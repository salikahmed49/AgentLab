import json
from io import BytesIO

import pytest

from backend.services import llm


@pytest.fixture(autouse=True)
def clear_selected_provider(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "auto")
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GROQ_API_KEY", raising=False)


def test_ollama_sends_chat_request_and_returns_content(monkeypatch):
    captured = {}

    def fake_urlopen(request, timeout):
        captured["url"] = request.full_url
        captured["body"] = json.loads(request.data)
        captured["timeout"] = timeout
        return BytesIO(b'{"message":{"content":"local result"}}')

    monkeypatch.setattr(llm, "urlopen", fake_urlopen)

    result = llm._generate_with_ollama("test prompt", "system instructions")

    assert result == "local result"
    assert captured["url"] == "http://127.0.0.1:11434/api/chat"
    assert captured["body"]["model"] == "qwen3:1.7b"
    assert captured["body"]["messages"] == [
        {"role": "system", "content": "system instructions"},
        {"role": "user", "content": "test prompt"},
    ]
    assert captured["body"]["stream"] is False
    assert captured["timeout"] == 90


def test_generate_response_uses_selected_ollama_provider(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "ollama")
    monkeypatch.setenv("GEMINI_API_KEY", "gemini-demo-key")
    monkeypatch.setenv("GROQ_API_KEY", "groq-demo-key")

    def fake_ollama(prompt, system_prompt):
        assert prompt == "test prompt"
        return "local result"

    monkeypatch.setattr(llm, "_generate_with_ollama", fake_ollama)

    assert llm.generate_response("test prompt") == "local result"


class FakeGroq:
    def __init__(self, api_key, **client_options):
        raise RuntimeError("provider unavailable")


def test_generate_response_raises_on_provider_failure(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "groq")
    monkeypatch.setenv("GROQ_API_KEY", "test-key")
    monkeypatch.setattr(llm, "Groq", FakeGroq)

    with pytest.raises(RuntimeError, match="provider unavailable|GROQ_API_KEY"):
        llm.generate_response("test prompt")


def test_generate_response_uses_gemini_when_groq_missing(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "gemini")
    monkeypatch.setenv("GEMINI_API_KEY", "gemini-demo-key")

    def fake_gemini(prompt, system_prompt):
        assert prompt == "test prompt"
        assert "research assistant" in system_prompt.lower()
        return "gemini result"

    monkeypatch.setattr(llm, "_generate_with_gemini", fake_gemini)

    assert llm.generate_response("test prompt") == "gemini result"


def test_auto_routing_falls_back_to_gemini_when_groq_fails(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "test-key")
    monkeypatch.setenv("GEMINI_API_KEY", "gemini-demo-key")

    calls = []

    def fake_groq(prompt, system_prompt):
        calls.append("groq")
        raise RuntimeError("provider rejected request")

    def fake_gemini(prompt, system_prompt):
        calls.append("gemini")
        return "fallback gemini result"

    monkeypatch.setattr(llm, "_generate_with_groq", fake_groq)
    monkeypatch.setattr(llm, "_generate_with_gemini", fake_gemini)

    assert llm.generate_response(
        "Summarize these findings.",
        system_prompt="You are the Research Agent.",
    ) == "fallback gemini result"
    assert calls == ["groq", "gemini"]


def test_auto_routing_uses_gemini_for_complex_analysis(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "test-key")
    monkeypatch.setenv("GEMINI_API_KEY", "gemini-demo-key")
    calls = []

    def fake_gemini(prompt, system_prompt):
        calls.append("gemini")
        return "gemini result"

    def fake_groq(prompt, system_prompt):
        calls.append("groq")
        return "groq result"

    monkeypatch.setattr(llm, "_generate_with_gemini", fake_gemini)
    monkeypatch.setattr(llm, "_generate_with_groq", fake_groq)

    result = llm.generate_response(
        "Compare the findings and evaluate conflicting evidence.",
        system_prompt="You are the Analysis Agent.",
    )

    assert result == "gemini result"
    assert calls == ["gemini"]


def test_auto_routing_keeps_confidential_input_local(monkeypatch):
    monkeypatch.setenv("AGENTLAB_PRIVACY_ROUTING", "true")
    monkeypatch.setenv("GROQ_API_KEY", "test-key")
    monkeypatch.setenv("GEMINI_API_KEY", "gemini-demo-key")
    calls = []

    def fake_ollama(prompt, system_prompt):
        calls.append("ollama")
        return "local result"

    monkeypatch.setattr(llm, "_generate_with_ollama", fake_ollama)
    monkeypatch.setattr(
        llm,
        "_generate_with_groq",
        lambda prompt, system_prompt: calls.append("groq"),
    )
    monkeypatch.setattr(
        llm,
        "_generate_with_gemini",
        lambda prompt, system_prompt: calls.append("gemini"),
    )

    assert llm.generate_response("Summarize this confidential document.") == "local result"
    assert calls == ["ollama"]


@pytest.mark.parametrize(
    ("prompt", "system_prompt", "expected_reason"),
    [
        ("A" * 30_000, "general task", "large context"),
        ("Create three questions.", "Follow-up Question Agent", "constrained question or citation task"),
    ],
)
def test_auto_routing_classifies_context_and_agent_intent(
    prompt, system_prompt, expected_reason
):
    _, reason = llm._automatic_provider_order(prompt, system_prompt)

    assert reason == expected_reason


def test_auto_routing_prefers_cloud_for_fast_constrained_tasks(monkeypatch):
    monkeypatch.delenv("AGENTLAB_PRIVACY_ROUTING", raising=False)

    providers, reason = llm._automatic_provider_order(
        "Create three follow-up questions.",
        "You are the Follow-up Question Agent.",
    )

    assert providers == ["groq", "gemini", "ollama"]
    assert reason == "constrained question or citation task"


def test_generate_response_truncates_large_prompts():
    huge_prompt = "A" * 250000

    truncated = llm._truncate_for_context(huge_prompt)

    assert len(truncated) < 150000
    assert "...[truncated" in truncated


def test_privacy_routing_is_off_by_default(monkeypatch):
    monkeypatch.setenv("AGENTLAB_PRIVACY_ROUTING", "false")
    monkeypatch.setenv("GROQ_API_KEY", "test-key")
    monkeypatch.setenv("GEMINI_API_KEY", "gemini-demo-key")
    calls = []

    monkeypatch.setattr(
        llm,
        "_generate_with_ollama",
        lambda prompt, system_prompt: calls.append("ollama"),
    )
    monkeypatch.setattr(
        llm,
        "_generate_with_groq",
        lambda prompt, system_prompt: "cloud result",
    )

    assert llm.generate_response("Summarize this confidential document.") == "cloud result"
    assert "ollama" not in calls
