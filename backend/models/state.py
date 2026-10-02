from typing_extensions import TypedDict

from backend.models.research import SearchResult


class ResearchState(TypedDict):
    topic: str
    research: str
    analysis: str
    verification: str
    report: str
    sources: list[SearchResult]