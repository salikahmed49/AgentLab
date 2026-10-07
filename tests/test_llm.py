import asyncio

import pytest

from backend.services import llm


@pytest.fixture(autouse=True)
def clear_provider_settings(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "auto")
    monkeypatch.setenv("AGENTLAB_PRIVACY_ROUTING", "false")
    for key in ("GEMINI_API_KEY", "GROQ_API_KEY"):
        monkeypatch.delenv(key, raising=False)


def test_groq_uses_stage_model_json_mode_token_limit_and_async_client(monkeypatch):
    captured = {}

    class Message:
        content = '{"key_findings":["grounded"]}'

    class Usage:
        prompt_tokens = 120
        completion_tokens = 30

    class Response:
        choices = [type("Choice", (), {"message": Message()})()]
        usage = Usage()

    class Completions:
        async def create(self, **options):
            captured["options"] = options
            return Response()

    class FakeAsyncGroq:
        def __init__(self, **options):
            captured["client_options"] = options
            self.chat = type("Chat", (), {"completions": Completions()})()

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

    monkeypatch.setenv("GROQ_API_KEY", "test-key")
    monkeypatch.setenv("GROQ_FAST_MODEL", "fast-test-model")
    monkeypatch.setattr(llm, "AsyncGroq", FakeAsyncGroq)

    result = asyncio.run(
        llm.agenerate_response(
            "Analyze evidence.",
            stage="analysis",
            response_format="json",
            max_output_tokens=900,
        )
    )

    assert result == '{"key_findings":["grounded"]}'
    assert captured["client_options"]["max_retries"] == 0
    assert captured["options"]["model"] == "fast-test-model"
    assert captured["options"]["max_completion_tokens"] == 900
    assert captured["options"]["response_format"] == {"type": "json_object"}


def test_auto_routing_falls_back_from_groq_to_gemini(monkeypatch):
    calls = []

    async def failing_groq(*args):
        calls.append("groq")
        raise RuntimeError("provider rejected request")

    async def fake_gemini(*args):
        calls.append("gemini")
        return "fallback result", 20, 10

    monkeypatch.setenv("GROQ_API_KEY", "groq-test-key")
    monkeypatch.setenv("GEMINI_API_KEY", "gemini-test-key")
    monkeypatch.setenv("LLM_PROVIDER", "groq")
    monkeypatch.setattr(llm, "_call_groq", failing_groq)
    monkeypatch.setattr(llm, "_call_gemini", fake_gemini)

    result = asyncio.run(
        llm.agenerate_response("Analyze findings.", stage="analysis")
    )

    assert result == "fallback result"
    assert calls == ["groq", "gemini"]


def test_analysis_uses_fast_groq_first_and_report_uses_gemini_first():
    assert llm._provider_order("analysis", "short", "analysis") == [
        "groq",
        "gemini",
    ]
    assert llm._provider_order("verification", "short", "verify") == [
        "groq",
        "gemini",
    ]
    assert llm._provider_order("report", "short", "report") == [
        "gemini",
        "groq",
        "ollama",
    ]


def test_analysis_keeps_gemini_fallback_when_groq_is_pinned(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "groq")

    assert llm._provider_order("analysis", "short", "analysis") == [
        "groq",
        "gemini",
    ]


@pytest.mark.parametrize(
    ("provider", "expected"),
    [
        ("groq", ["groq", "gemini"]),
        ("gemini", ["gemini", "groq"]),
    ],
)
def test_verification_keeps_cloud_fallback_when_provider_is_pinned(
    monkeypatch, provider, expected
):
    monkeypatch.setenv("LLM_PROVIDER", provider)

    assert llm._provider_order("verification", "short", "verify") == expected


def test_ollama_is_not_tried_without_explicit_configuration(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "groq-test-key")
    monkeypatch.setenv("GEMINI_API_KEY", "gemini-test-key")
    monkeypatch.delenv("OLLAMA_HOST", raising=False)
    calls = []

    async def failing_groq(*args):
        calls.append("groq")
        raise RuntimeError("Groq unavailable")

    async def failing_gemini(*args):
        calls.append("gemini")
        raise RuntimeError("Gemini unavailable")

    async def unexpected_ollama(*args):
        calls.append("ollama")
        raise RuntimeError("Ollama should not be tried")

    monkeypatch.setattr(llm, "_call_groq", failing_groq)
    monkeypatch.setattr(llm, "_call_gemini", failing_gemini)
    monkeypatch.setattr(llm, "_call_ollama", unexpected_ollama)

    with pytest.raises(llm.LLMProviderError, match="All automatic LLM providers failed"):
        asyncio.run(
            llm.agenerate_response("Verify claims.", stage="verification")
        )
    assert calls == ["groq", "gemini"]


def test_privacy_routing_stays_local(monkeypatch):
    calls = []

    async def fake_ollama(*args):
        calls.append("ollama")
        return "local result", None, None

    async def unexpected_cloud(*args):
        calls.append("cloud")
        return "cloud result", None, None

    monkeypatch.setenv("AGENTLAB_PRIVACY_ROUTING", "true")
    monkeypatch.setenv("GROQ_API_KEY", "groq-test-key")
    monkeypatch.setenv("GEMINI_API_KEY", "gemini-test-key")
    monkeypatch.setattr(llm, "_call_ollama", fake_ollama)
    monkeypatch.setattr(llm, "_call_groq", unexpected_cloud)
    monkeypatch.setattr(llm, "_call_gemini", unexpected_cloud)

    result = asyncio.run(
        llm.agenerate_response("Summarize this confidential document.")
    )

    assert result == "local result"
    assert calls == ["ollama"]


def test_only_429_and_5xx_are_retried(monkeypatch):
    calls = []

    class RateLimitError(Exception):
        status_code = 429

    async def fake_groq(*args):
        calls.append(1)
        if len(calls) == 1:
            raise RateLimitError()
        return "success", 1, 1

    async def no_sleep(_seconds):
        return None

    monkeypatch.setattr(llm, "_call_groq", fake_groq)
    monkeypatch.setattr(llm.asyncio, "sleep", no_sleep)

    text, input_tokens, output_tokens = asyncio.run(
        llm._call_provider("groq", "prompt", "system", "analysis", None, 100)
    )

    assert (text, input_tokens, output_tokens) == ("success", 1, 1)
    assert len(calls) == 2


def test_large_context_prefers_gemini():
    providers = llm._provider_order("research", "x" * 30_000, "research")

    assert providers[0] == "gemini"


def test_truncate_for_context():
    huge_prompt = "A" * 250_000

    truncated = llm._truncate_for_context(huge_prompt)

    assert len(truncated) < 150_000
    assert "...[truncated" in truncated
