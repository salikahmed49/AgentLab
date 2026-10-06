from collections.abc import Callable

from typing_extensions import NotRequired, TypedDict

from backend.models.research import SearchResult


class ResearchState(TypedDict):
    topic: str
    research: str
    analysis: str
    verification: str
    report: str
    sources: list[SearchResult]
    citations: list[dict]
    follow_up_questions: list[str]
    document_context: str
    documents: list[str]
    on_step: NotRequired[Callable[[str, str], None] | None]
    on_result: NotRequired[Callable[[str, object], None] | None]