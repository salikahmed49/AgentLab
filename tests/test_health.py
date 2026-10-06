import pytest
from fastapi.testclient import TestClient

from backend.main import _parse_cors_origins, app


client = TestClient(app)


def test_cors_origins_trim_whitespace_and_trailing_slashes():
    assert _parse_cors_origins(
        " https://agent.example/ , https://preview.example "
    ) == ["https://agent.example", "https://preview.example"]


@pytest.fixture(autouse=True)
def clear_selected_provider(monkeypatch):
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GROQ_API_KEY", raising=False)


def test_health_reports_runtime_configuration(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "demo-key")
    monkeypatch.setenv("TAVILY_API_KEY", "demo-key")

    response = client.get("/health")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "healthy"
    assert payload["checks"]["groq"] is True
    assert payload["checks"]["tavily"] is True


def test_health_reports_degraded_state_when_keys_missing(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "gemini")
    monkeypatch.delenv("TAVILY_API_KEY", raising=False)
    monkeypatch.setattr("backend.main.ollama_model_available", lambda: False)

    response = client.get("/health")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "degraded"
    assert payload["checks"]["groq"] is False
    assert payload["checks"]["gemini"] is False
    assert payload["checks"]["tavily"] is False


def test_health_accepts_gemini_as_llm_provider(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "gemini")
    monkeypatch.setenv("GEMINI_API_KEY", "demo-key")
    monkeypatch.setenv("TAVILY_API_KEY", "demo-key")

    response = client.get("/health")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "healthy"
    assert payload["checks"]["groq"] is False
    assert payload["checks"]["gemini"] is True
    assert payload["checks"]["tavily"] is True


def test_health_reports_selected_ollama_provider(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "ollama")
    monkeypatch.setenv("TAVILY_API_KEY", "demo-key")
    monkeypatch.setattr("backend.main.ollama_model_available", lambda: True)

    response = client.get("/health")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "healthy"
    assert payload["checks"]["ollama"] is True
    assert payload["checks"]["provider"] == "ollama"


def test_health_reports_automatic_routing_when_a_provider_is_available(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "auto")
    monkeypatch.setenv("TAVILY_API_KEY", "demo-key")
    monkeypatch.setattr("backend.main.ollama_model_available", lambda: True)

    response = client.get("/health")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "healthy"
    assert payload["checks"]["llm"] is True
    assert payload["checks"]["provider"] == "auto"
    assert payload["checks"]["ollama"] is True


def test_api_rate_limit_blocks_excessive_requests():
    app.state.rate_limit_window_seconds = 60
    app.state.rate_limit_max_requests = 2
    app.state.rate_limit_buckets = {}

    for _ in range(2):
        response = client.get("/")
        assert response.status_code == 200

    response = client.get("/")

    assert response.status_code == 429
    payload = response.json()
    assert payload["error"] == "rate_limited"