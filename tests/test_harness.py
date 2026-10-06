from fastapi.testclient import TestClient

from backend.main import app
from backend.services.harness import StepFailedError, run_step


def test_run_step_returns_result_on_success():
    assert run_step("demo", lambda: "ok") == "ok"


def test_run_step_retries_then_succeeds():
    calls = []

    def flaky():
        calls.append(1)
        if len(calls) < 3:
            raise ValueError("temporary problem")
        return "recovered"

    result = run_step("demo", flaky, retries=2, wait_seconds=0)

    assert result == "recovered"
    assert len(calls) == 3


def test_run_step_raises_after_all_retries():
    calls = []

    def always_fails():
        calls.append(1)
        raise ValueError("still broken")

    try:
        run_step("demo", always_fails, retries=2, wait_seconds=0)
        assert False, "should have raised StepFailedError"
    except StepFailedError as error:
        assert error.step_name == "demo"

    assert len(calls) == 3


def test_run_step_does_not_retry_missing_config():
    calls = []

    def missing_key():
        calls.append(1)
        raise RuntimeError("GROQ_API_KEY is not configured")

    try:
        run_step("demo", missing_key, retries=2, wait_seconds=0)
        assert False, "should have raised StepFailedError"
    except StepFailedError:
        pass

    assert len(calls) == 1


def test_research_endpoint_returns_502_when_a_step_fails(monkeypatch):
    def fake_research(topic):
        raise StepFailedError("analysis", RuntimeError("boom"))

    monkeypatch.setattr("backend.main.perform_research", fake_research)

    client = TestClient(app)
    response = client.post("/research", json={"topic": "test"})

    assert response.status_code == 502
    assert response.json()["step"] == "analysis"
