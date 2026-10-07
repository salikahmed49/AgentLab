import time
from threading import Event

from fastapi.testclient import TestClient

from backend.main import app


client = TestClient(app)


class FakeGraph:
    """Stands in for the real LangGraph pipeline. Makes no API calls."""

    def invoke(self, state):
        return {
            "topic": state["topic"],
            "research": "fake research",
            "analysis": "fake analysis",
            "verification": "fake verification",
            "report": "# Fake report",
            "sources": [
                {
                    "title": "Test Result",
                    "url": "https://example.com",
                    "content": "This is test research content.",
                    "score": 0.95,
                }
            ],
        }


def test_research_returns_full_report(monkeypatch):
    monkeypatch.setattr("backend.services.research.research_graph", FakeGraph())

    response = client.post("/research", json={"topic": "Artificial Intelligence"})

    assert response.status_code == 200

    data = response.json()

    assert data["topic"] == "Artificial Intelligence"
    assert data["status"] == "completed"
    assert data["report"] == "# Fake report"
    assert len(data["sources"]) == 1
    assert data["sources"][0]["url"] == "https://example.com"


def test_research_rejects_missing_topic():
    response = client.post("/research", json={})

    assert response.status_code == 422


def test_upload_documents_returns_extracted_text():
    response = client.post(
        "/documents/upload",
        files={"files": ("notes.txt", "Alpha beta gamma\nThis is from a document.", "text/plain")},
    )

    assert response.status_code == 200
    data = response.json()
    assert len(data["documents"]) == 1
    assert data["documents"][0]["name"] == "notes.txt"
    assert "Alpha beta gamma" in data["documents"][0]["content"]


def test_research_accepts_document_context(monkeypatch):
    def fake_research(topic, documents=None):
        return {
            "topic": topic,
            "status": "completed",
            "research": "fake research",
            "analysis": "fake analysis",
            "verification": "fake verification",
            "report": "# Fake report",
            "sources": [],
            "citations": [],
            "follow_up_questions": [],
            "documents": documents or [],
        }

    monkeypatch.setattr("backend.main.perform_research", fake_research)

    response = client.post(
        "/research",
        json={
            "topic": "Artificial Intelligence",
            "documents": [
                {"name": "brief.txt", "content": "AI is a broad field of computer science.", "size": 42}
            ],
        },
    )

    assert response.status_code == 200
    assert response.json()["topic"] == "Artificial Intelligence"


def test_research_job_tracks_progress_and_publishes_partial_results(monkeypatch):
    partial_results_published = Event()

    def fake_research(topic, documents=None, on_step=None, on_result=None):
        if on_step:
            on_step("research", "processing")
        if on_result:
            on_result("research", {"research": "Early research", "sources": []})
            on_result("analysis", "Early analysis")
            partial_results_published.set()
        time.sleep(0.01)
        if on_step:
            on_step("research", "completed")
            on_step("analysis", "processing")
            time.sleep(0.01)
            on_step("analysis", "completed")

        return {
            "topic": topic,
            "status": "completed",
            "research": "fake research",
            "analysis": "fake analysis",
            "verification": "fake verification",
            "report": "# Fake job report",
            "sources": [],
            "documents": documents or [],
        }

    monkeypatch.setattr("backend.main.perform_research", fake_research)

    response = client.post("/research/jobs", json={"topic": "AI"})
    assert response.status_code == 200

    job = response.json()
    assert "job_id" in job
    assert job["status"] == "queued"
    assert partial_results_published.wait(timeout=2)

    status = client.get(f"/research/jobs/{job['job_id']}")
    assert status.status_code == 200
    payload = status.json()
    assert payload["status"] in {"running", "completed"}
    assert payload["job_id"] == job["job_id"]
    assert payload["partial_result"]["research"] == "Early research"
    assert payload["partial_result"]["analysis"] == "Early analysis"


def test_research_returns_citations_and_follow_up_questions(monkeypatch):
    monkeypatch.setattr(
        "backend.services.research.research_graph",
        type(
            "FakeGraph",
            (),
            {
                "invoke": lambda self, state: {
                    "topic": state["topic"],
                    "research": "fake research",
                    "analysis": "fake analysis",
                    "verification": "fake verification",
                    "report": "# Fake report",
                    "sources": [
                        {
                            "title": "Test Result",
                            "url": "https://example.com",
                            "content": "This is test research content.",
                            "score": 0.95,
                        }
                    ],
                    "citations": [
                        {
                            "claim": "AI trend is accelerating.",
                            "source_title": "Test Result",
                            "source_url": "https://example.com",
                            "quote": "This is test research content.",
                        }
                    ],
                    "follow_up_questions": [
                        "What are the biggest risks in this market?",
                        "Which companies are leading the space?",
                    ],
                }
            },
        )(),
    )

    response = client.post("/research", json={"topic": "Artificial Intelligence"})

    assert response.status_code == 200
    data = response.json()
    assert len(data["citations"]) == 1
    assert data["citations"][0]["source_url"] == "https://example.com"
    assert len(data["follow_up_questions"]) == 2
    assert "risks" in data["follow_up_questions"][0].lower()


def test_research_stream_emits_progress_sections_and_final_response(monkeypatch):
    def fake_research(
        topic,
        documents=None,
        on_step=None,
        on_result=None,
        on_report_chunk=None,
    ):
        if on_step:
            on_step("research", "processing")
        if on_result:
            on_result(
                "research",
                {"research": "Research notes", "sources": []},
            )
        if on_step:
            on_step("research", "completed")
        if on_report_chunk:
            on_report_chunk(0, "Executive Summary", "A short summary.")
        return {
            "topic": topic,
            "status": "completed",
            "research": "Research notes",
            "analysis": "Analysis notes",
            "verification": "Verification notes",
            "report": "# Test topic\n\n## Executive Summary\n\nA short summary.",
            "sources": [],
            "citations": [],
            "follow_up_questions": [],
            "documents": documents or [],
        }

    monkeypatch.setattr("backend.main.perform_research", fake_research)

    response = client.post(
        "/research/stream",
        json={"topic": "Test topic"},
        headers={"Origin": "http://localhost:3000"},
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert response.headers["access-control-allow-origin"] == "http://localhost:3000"
    assert "event: progress" in response.text
    assert "event: partial_result" in response.text
    assert "event: report_section" in response.text
    assert "A short summary." in response.text
    assert "event: complete" in response.text
