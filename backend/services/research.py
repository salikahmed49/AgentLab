from backend.models.research import SearchResult
from backend.tools.web_search import search_web


def perform_research(topic: str) -> dict:
    results: list[SearchResult] = search_web(topic)

    return {
        "topic": topic,
        "status": "completed",
        "results": results
    }