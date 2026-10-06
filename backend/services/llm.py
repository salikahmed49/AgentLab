import json
import logging
import os
import re
import time
from collections.abc import Callable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from dotenv import load_dotenv

try:
    from groq import Groq
except ImportError:  # pragma: no cover - only used when the dependency is absent.
    Groq = None


logger = logging.getLogger("agentlab")
load_dotenv()


class LLMProviderError(RuntimeError):
    pass


MAX_CONTEXT_CHARS = 120_000


def _truncate_for_context(text: str, max_chars: int = MAX_CONTEXT_CHARS) -> str:
    if len(text) <= max_chars:
        return text
    suffix = "...[truncated to fit model context window]"
    trimmed = text[: max_chars - len(suffix)]
    return f"{trimmed.rstrip()} {suffix}"


def _is_transient_provider_error(error: Exception) -> bool:
    message = str(error).lower()
    transient_tokens = (
        "rate limit",
        "rate_limit",
        "429",
        "503",
        "unavailable",
        "temporar",
        "high demand",
        "overloaded",
        "resource exhausted",
        "try again later",
    )
    return any(token in message for token in transient_tokens)


def _with_retry(
    provider_name: str,
    provider_callable: Callable[[str, str], str],
    prompt: str,
    system_prompt: str,
    max_attempts: int = 3,
) -> str:
    last_error: Exception | None = None
    for attempt in range(1, max_attempts + 1):
        try:
            return provider_callable(prompt, system_prompt)
        except Exception as error:
            last_error = error
            if not _is_transient_provider_error(error) or attempt == max_attempts:
                raise
            logger.warning(
                "provider_retry %s attempt=%d/%d error=%s",
                provider_name,
                attempt,
                max_attempts,
                type(error).__name__,
            )
            time.sleep(attempt * 1.5)
    if last_error is not None:
        raise last_error
    raise LLMProviderError(f"{provider_name} failed without returning a result.")


def _generate_with_groq(prompt: str, system_prompt: str) -> str:
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise LLMProviderError("GROQ_API_KEY is not configured")
    if Groq is None:
        raise LLMProviderError("The Groq SDK is not installed in this environment.")

    prompt = _truncate_for_context(prompt, MAX_CONTEXT_CHARS - 20_000)
    system_prompt = _truncate_for_context(system_prompt, 20_000)

    model = os.getenv("GROQ_MODEL", "openai/gpt-oss-20b")
    extra = {"max_completion_tokens": int(os.getenv("GROQ_MAX_TOKENS", "2500"))}
    if model.startswith("openai/gpt-oss"):
        extra["reasoning_effort"] = os.getenv("GROQ_REASONING_EFFORT", "low")

    client = Groq(api_key=api_key, max_retries=1, timeout=60)
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt},
        ],
        extra_body=extra,
    )

    content = response.choices[0].message.content
    if content is None:
        raise LLMProviderError("The AI provider returned an empty response.")
    return content


def _generate_with_gemini(prompt: str, system_prompt: str) -> str:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise LLMProviderError("GEMINI_API_KEY is not configured")

    try:
        from google import genai
    except ImportError as error:
        raise LLMProviderError(
            "The Gemini SDK is not installed. Install google-genai to use GEMINI_API_KEY."
        ) from error

    client = genai.Client(api_key=api_key)
    combined_prompt = _truncate_for_context(f"{system_prompt}\n\n{prompt}", MAX_CONTEXT_CHARS)
    response = client.models.generate_content(
        model="gemini-3.8-flash",
        contents=combined_prompt,
    )

    text = getattr(response, "text", None)
    if text:
        return text

    if hasattr(response, "candidates") and response.candidates:
        parts = getattr(response.candidates[0], "content", None)
        if parts is not None:
            extracted = []
            for part in getattr(parts, "parts", []) or []:
                if getattr(part, "text", None):
                    extracted.append(part.text)
            joined = "".join(extracted)
            if joined:
                return joined

    raise LLMProviderError("The Gemini API returned an empty response.")


def _generate_with_ollama(prompt: str, system_prompt: str) -> str:
    host = os.getenv("OLLAMA_HOST", "http://127.0.0.1:11434").rstrip("/")
    model = os.getenv("OLLAMA_MODEL", "qwen3:1.7b")
    request = Request(
        f"{host}/api/chat",
        data=json.dumps(
            {
                "model": model,
                "messages": [
                    {"role": "system", "content": _truncate_for_context(system_prompt, 20_000)},
                    {
                        "role": "user",
                        "content": _truncate_for_context(prompt, MAX_CONTEXT_CHARS - 20_000),
                    },
                ],
                "stream": False,
                "think": False,
                "options": {"num_ctx": 32_768},
            }
        ).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urlopen(request, timeout=90) as response:
            payload = json.load(response)
    except HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace").strip()
        raise LLMProviderError(
            f"Ollama returned HTTP {error.code}: {detail or error.reason}"
        ) from error
    except URLError as error:
        raise LLMProviderError(
            "Cannot connect to Ollama. Start the Ollama app and verify OLLAMA_HOST."
        ) from error

    message = payload.get("message") if isinstance(payload, dict) else None
    content = message.get("content") if isinstance(message, dict) else None
    if isinstance(content, str) and content:
        return content
    raise LLMProviderError("Ollama returned an empty response.")


def ollama_model_available() -> bool:
    host = os.getenv("OLLAMA_HOST", "http://127.0.0.1:11434").rstrip("/")
    model = os.getenv("OLLAMA_MODEL", "qwen3:1.7b")
    request = Request(f"{host}/api/tags")

    try:
        with urlopen(request, timeout=1.5) as response:
            payload = json.load(response)
    except (OSError, URLError, TimeoutError, ValueError) as error:
        logger.debug("ollama_health_check_failed: %s", type(error).__name__)
        return False

    models = payload.get("models", []) if isinstance(payload, dict) else []
    return any(
        isinstance(item, dict)
        and model in {item.get("name"), item.get("model")}
        for item in models
    )


def _automatic_provider_order(prompt: str, system_prompt: str) -> tuple[list[str], str]:
    task = system_prompt.lower()
    content = prompt.lower()
    privacy_patterns = (
        r"\bkeep (?:this|the data|the documents?) local\b",
        r"\blocal only\b",
        r"\bdo not send (?:this|the data|the documents?) to (?:the )?cloud\b",
        r"\bconfidential\b",
        r"\bprivate\b",
        r"\bpersonal data\b",
        r"\bpatient records?\b",
        r"\bmedical records?\b",
        r"\baccount numbers?\b",
        r"\bsocial security numbers?\b",
        r"\bpassport numbers?\b",
    )
    privacy_routing = os.getenv("AGENTLAB_PRIVACY_ROUTING", "false").lower() == "true"
    if privacy_routing and any(re.search(pattern, content) for pattern in privacy_patterns):
        return ["ollama"], "privacy-sensitive or explicitly local-only input"

    if len(prompt) >= 30_000:
        return ["gemini", "groq", "ollama"], "large context"

    complex_intent_terms = (
        "compare",
        "contrast",
        "evaluate",
        "trade-off",
        "tradeoff",
        "causal",
        "forecast",
        "predict",
        "multi-step",
        "competing explanations",
        "conflicting evidence",
    )
    if (
        "analysis agent" in task
        or "verification agent" in task
        or any(re.search(rf"\b{re.escape(term)}\b", content) for term in complex_intent_terms)
    ):
        return ["gemini", "groq", "ollama"], "complex analysis or verification"

    if "follow-up question agent" in task or "citation and evidence linker agent" in task:
        return ["groq", "gemini", "ollama"], "constrained question or citation task"

    if "research agent" in task or "report agent" in task:
        return ["groq", "gemini", "ollama"], "research synthesis or report drafting"

    return ["groq", "gemini", "ollama"], "general task"


def _generate_automatically(prompt: str, system_prompt: str) -> str:
    provider_functions: dict[str, Callable[[str, str], str]] = {
        "gemini": _generate_with_gemini,
        "groq": _generate_with_groq,
        "ollama": _generate_with_ollama,
    }
    configured = {
        "gemini": bool(os.getenv("GEMINI_API_KEY")),
        "groq": bool(os.getenv("GROQ_API_KEY")),
        "ollama": True,
    }
    preferred_order, reason = _automatic_provider_order(prompt, system_prompt)
    providers = [
        name for name in preferred_order
        if configured[name] and (name != "groq" or Groq is not None)
    ]
    if not providers:
        raise LLMProviderError(
            "No LLM provider is available. Configure Ollama or set GEMINI_API_KEY/GROQ_API_KEY."
        )

    errors: list[tuple[str, Exception]] = []
    for index, provider_name in enumerate(providers):
        if index == 0:
            logger.info("llm_route provider=%s reason=%s", provider_name, reason)
        try:
            return _with_retry(
                provider_name,
                provider_functions[provider_name],
                prompt,
                system_prompt,
            )
        except Exception as error:
            errors.append((provider_name, error))
            logger.warning(
                "llm_provider_failed provider=%s error=%s",
                provider_name,
                type(error).__name__,
            )
            if reason.startswith("privacy-sensitive"):
                raise LLMProviderError(
                    "Local-only processing was requested, but Ollama is unavailable."
                ) from error

    failed_providers = ", ".join(name for name, _ in errors)
    last_error = errors[-1][1]
    raise LLMProviderError(
        f"All automatic LLM providers failed ({failed_providers}): {last_error}"
    ) from last_error


def generate_response(
    prompt: str,
    system_prompt: str = "You are a helpful research assistant."
) -> str:
    selected_provider = os.getenv("LLM_PROVIDER", "auto").strip().lower() or "auto"
    if selected_provider == "auto":
        return _generate_automatically(prompt, system_prompt)

    providers = {
        "gemini": ("GEMINI_API_KEY", _generate_with_gemini),
        "groq": ("GROQ_API_KEY", _generate_with_groq),
        "ollama": (None, _generate_with_ollama),
    }
    if selected_provider not in providers:
        raise LLMProviderError(
            "LLM_PROVIDER must be auto, gemini, groq, or ollama."
        )
    required_key, provider = providers[selected_provider]
    if required_key and not os.getenv(required_key):
        raise LLMProviderError(f"{required_key} is not configured")
    return _with_retry(selected_provider, provider, prompt, system_prompt)