from pydantic import BaseModel


class ResearchRequest(BaseModel):
    topic: str


class SearchResult(BaseModel):
    title: str
    url: str
    content: str
    score: float


class ResearchResponse(BaseModel):
    topic: str
    status: str
    results: list[SearchResult]