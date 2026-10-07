import asyncio
import json
import logging
import os
import re
import time
from contextlib import asynccontextmanager
from contextvars import ContextVar
from urllib.error import URLError
from urllib.request import Request, urlopen

import httpx
from dotenv import load_dotenv
from groq import AsyncGroq

load_dotenv()

logger = logging.getLogger("agentlab")
MAX_CONTEXT_CHARS = 120_000
MAX_CONCURRENCY = 5
LLM_CALL_TIMEOUT_SECONDS = 30.0
_CALL_SEMAPHORE: ContextVar[asyncio.Semaphore | None] = ContextVar(
    "agentlab_llm_call_semaphore", default=None
)


class LLMProviderError(RuntimeError):
    pass


def _truncate_for_context(text: str, max_chars: int = MAX_CONTEXT_CHARS) -> str:
    if len(text) <= max_chars:
        return text
    suffix = "...[truncated to fit model context window]"
    return f"{text[: max_chars - len(suffix)].rstrip()} {suffix}"


def _is_retryable_error(error: Exception) -> bool:
    response = getattr(error, "response", None)
    status = (
        getattr(error, "status_code", None)
        or getattr(error, "code", None)
        or getattr(response, "status_code", None)
    )
    if status is not None:
        try:
            status_code = int(status)
        except (TypeError, ValueError):
            return False
        return status_code == 429 or 500 <= status_code <= 599
    return False


def _provider_order(stage: str, prompt: str, system_prompt: str) -> list[str]:
    privacy_routing = os.getenv("AGENTLAB_PRIVACY_ROUTING", "false").lower() == "true"
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
    if privacy_routing and any(re.search(pattern, prompt.lower()) for pattern in privacy_patterns):
        return ["ollama"]

    preferred_provider = os.getenv("LLM_PROVIDER", "auto").strip().lower() or "auto"
    if preferred_provider != "auto":
        if preferred_provider not in {"groq", "gemini", "ollama"}:
            raise LLMProviderError("LLM_PROVIDER must be auto, gemini, groq, or ollama.")
        return [preferred_provider]

    if len(prompt) >= 30_000:
        return ["gemini", "groq", "ollama"]
    if stage == "report":
        return ["gemini", "groq", "ollama"]
    if stage in {"analysis", "verification"}:
        return ["groq", "gemini", "ollama"]
    if stage in {"citation_linking", "follow_up_questions"}:
        return ["groq", "gemini", "ollama"]

    lowered_task = system_prompt.lower()
    if "analysis agent" in lowered_task or "verification agent" in lowered_task:
        return ["groq", "gemini", "ollama"]
    return ["groq", "gemini", "ollama"]


def _stage_model(provider: str, stage: str) -> str:
    if provider == "groq":
        if stage in {"analysis", "verification"}:
            return os.getenv(
                "GROQ_FAST_MODEL",
                os.getenv("GROQ_MODEL", "openai/gpt-oss-20b"),
            )
        return os.getenv("GROQ_MODEL", "openai/gpt-oss-20b")
    if provider == "gemini":
        return os.getenv("GEMINI_MODEL", "gemini-3.8-flash")
    return os.getenv("OLLAMA_MODEL", "qwen3:1.7b")


async def _call_groq(
    prompt: str,
    system_prompt: str,
    stage: str,
    response_format: str | None,
    max_output_tokens: int,
) -> tuple[str, int | None, int | None]:
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise LLMProviderError("GROQ_API_KEY is not configured")

    model = _stage_model("groq", stage)
    client = AsyncGroq(
        api_key=api_key,
        max_retries=0,
        timeout=LLM_CALL_TIMEOUT_SECONDS,
    )
    options: dict[str, object] = {
        "model": model,
        "messages": [
            {"role": "system", "content": _truncate_for_context(system_prompt, 20_000)},
            {
                "role": "user",
                "content": _truncate_for_context(prompt, MAX_CONTEXT_CHARS - 20_000),
            },
        ],
        "max_completion_tokens": max_output_tokens,
    }
    if response_format == "json":
        options["response_format"] = {"type": "json_object"}
    if model.startswith("openai/gpt-oss"):
        options["extra_body"] = {"reasoning_effort": "low"}

    async with client:
        response = await client.chat.completions.create(**options)
    content = response.choices[0].message.content
    if not content:
        raise LLMProviderError("The AI provider returned an empty response.")
    usage = getattr(response, "usage", None)
    return (
        content,
        getattr(usage, "prompt_tokens", None),
        getattr(usage, "completion_tokens", None),
    )


async def _call_gemini(
    prompt: str,
    system_prompt: str,
    stage: str,
    response_format: str | None,
    max_output_tokens: int,
) -> tuple[str, int | None, int | None]:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise LLMProviderError("GEMINI_API_KEY is not configured")

    try:
        from google import genai
        from google.genai import types
    except ImportError as error:  # pragma: no cover - dependency is required in production.
        raise LLMProviderError(
            "The Gemini SDK is not installed. Install google-genai to use GEMINI_API_KEY."
        ) from error

    client = genai.Client(
        api_key=api_key,
        http_options=types.HttpOptions(
            timeout=int(LLM_CALL_TIMEOUT_SECONDS * 1000),
            retry_options=types.HttpRetryOptions(attempts=1),
        ),
    )
    config: dict[str, object] = {"max_output_tokens": max_output_tokens}
    if response_format == "json":
        config["response_mime_type"] = "application/json"
    if stage not in {"analysis", "verification"}:
        config["thinking_config"] = {"thinking_budget": 0}

    try:
        response = await client.aio.models.generate_content(
            model=_stage_model("gemini", stage),
            contents=_truncate_for_context(
                f"{system_prompt}\n\n{prompt}", MAX_CONTEXT_CHARS
            ),
            config=config,
        )
    finally:
        await client.aio.aclose()

    try:
        text = getattr(response, "text", None)
    except (AttributeError, ValueError):
        text = None
    if not text:
        candidates = getattr(response, "candidates", None) or []
        for candidate in candidates:
            content = getattr(candidate, "content", None)
            parts = getattr(content, "parts", None) or []
            text = "".join(
                part_text
                for part in parts
                if (part_text := getattr(part, "text", None))
            )
            if text:
                break
    if not text:
        raise LLMProviderError("The Gemini API returned an empty response.")
    usage = getattr(response, "usage_metadata", None)
    return (
        text,
        getattr(usage, "prompt_token_count", None),
        getattr(usage, "candidates_token_count", None),
    )


async def _call_ollama(
    prompt: str,
    system_prompt: str,
    stage: str,
    response_format: str | None,
    max_output_tokens: int,
) -> tuple[str, int | None, int | None]:
    host = os.getenv("OLLAMA_HOST", "http://127.0.0.1:11434").rstrip("/")
    body: dict[str, object] = {
        "model": _stage_model("ollama", stage),
        "messages": [
            {"role": "system", "content": _truncate_for_context(system_prompt, 20_000)},
            {
                "role": "user",
                "content": _truncate_for_context(prompt, MAX_CONTEXT_CHARS - 20_000),
            },
        ],
        "stream": False,
        "think": False,
        "options": {"num_ctx": 32_768, "num_predict": max_output_tokens},
    }
    if response_format == "json":
        body["format"] = "json"

    async with httpx.AsyncClient(timeout=LLM_CALL_TIMEOUT_SECONDS) as client:
        response = await client.post(f"{host}/api/chat", json=body)
        response.raise_for_status()
        payload = response.json()
    message = payload.get("message") if isinstance(payload, dict) else None
    content = message.get("content") if isinstance(message, dict) else None
    if not isinstance(content, str) or not content:
        raise LLMProviderError("Ollama returned an empty response.")
    return content, payload.get("prompt_eval_count"), payload.get("eval_count")


async def _call_provider(
    provider: str,
    prompt: str,
    system_prompt: str,
    stage: str,
    response_format: str | None,
    max_output_tokens: int,
) -> tuple[str, int | None, int | None]:
    call = {
        "groq": _call_groq,
        "gemini": _call_gemini,
        "ollama": _call_ollama,
    }[provider]
    last_error: Exception | None = None
    for attempt in range(3):
        started = time.perf_counter()
        try:
            result = await call(
                prompt,
                system_prompt,
                stage,
                response_format,
                max_output_tokens,
            )
            logger.info(
                "llm_call provider=%s stage=%s seconds=%.2f input_tokens=%s output_tokens=%s status=ok",
                provider,
                stage,
                time.perf_counter() - started,
                result[1] if result[1] is not None else "unavailable",
                result[2] if result[2] is not None else "unavailable",
            )
            return result
        except Exception as error:
            last_error = error
            logger.warning(
                "llm_call provider=%s stage=%s seconds=%.2f status=failed error=%s",
                provider,
                stage,
                time.perf_counter() - started,
                type(error).__name__,
            )
            if not _is_retryable_error(error) or attempt == 2:
                raise
            await asyncio.sleep(min(0.25 * (2**attempt), 1.0))
    if last_error is not None:
        raise last_error
    raise LLMProviderError(f"{provider} failed without returning a result.")


@asynccontextmanager
async def llm_concurrency_limit(limit: int = MAX_CONCURRENCY):
    current = _CALL_SEMAPHORE.get()
    if current is not None:
        yield current
        return

    semaphore = asyncio.Semaphore(limit)
    token = _CALL_SEMAPHORE.set(semaphore)
    try:
        yield semaphore
    finally:
        _CALL_SEMAPHORE.reset(token)


async def agenerate_response(
    prompt: str,
    system_prompt: str = "You are a helpful research assistant.",
    *,
    stage: str = "general",
    response_format: str | None = None,
    max_output_tokens: int = 1200,
) -> str:
    providers = _provider_order(stage, prompt, system_prompt)
    configured = {
        "groq": bool(os.getenv("GROQ_API_KEY")),
        "gemini": bool(os.getenv("GEMINI_API_KEY")),
        "ollama": True,
    }
    candidates = [name for name in providers if configured[name]]
    if not candidates:
        raise LLMProviderError(
            "No LLM provider is available. Configure Ollama or set GEMINI_API_KEY/GROQ_API_KEY."
        )

    async with llm_concurrency_limit() as semaphore:
        errors: list[tuple[str, Exception]] = []
        for provider in candidates:
            try:
                async with semaphore:
                    text, _, _ = await _call_provider(
                        provider,
                        prompt,
                        system_prompt,
                        stage,
                        response_format,
                        max_output_tokens,
                    )
                return text
            except Exception as error:
                errors.append((provider, error))
                logger.warning(
                    "llm_provider_failed provider=%s stage=%s error=%s",
                    provider,
                    stage,
                    type(error).__name__,
                )
                if providers == ["ollama"]:
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
    system_prompt: str = "You are a helpful research assistant.",
    **options,
) -> str:
    """Synchronous compatibility wrapper; all provider calls use async clients."""
    return asyncio.run(
        agenerate_response(prompt, system_prompt, **options)
    )


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
