from fastapi.testclient import TestClient

from backend.main import app
from backend.services import research as research_service


client = TestClient(app)


def test_research():
    def fake_search_web(topic: str):
        return [
            {
                "title": "Test Result",
                "url": "https://example.com",
                "content": "This is test research content.",
                "score": 0.95,
            }
        ]

    research_service.search_web = fake_search_web

    response = client.post(
        "/research",
        json={"topic": "Artificial Intelligence"},
    )

    assert response.status_code == 200

    data = response.json()

    assert data["topic"] == "Artificial Intelligence"
    assert data["status"] == "completed"
    assert len(data["results"]) == 1
    assert data["results"][0]["title"] == "Test Result"