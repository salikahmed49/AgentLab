from pydantic import BaseModel, Field


class DocumentReference(BaseModel):
    name: str
    content: str = ""
    size: int = 0
    type: str = ""


class ResearchRequest(BaseModel):
    topic: str
    documents: list[DocumentReference] = Field(default_factory=list)


class SearchResult(BaseModel):
    title: str
    url: str
    content: str
    score: float


class EvidenceCitation(BaseModel):
    claim: str
    source_title: str
    source_url: str
    quote: str


class ResearchResponse(BaseModel):
    topic: str
    status: str
    research: str
    analysis: str
    verification: str
    report: str
    sources: list[SearchResult]
    citations: list[EvidenceCitation] = Field(default_factory=list)
    follow_up_questions: list[str] = Field(default_factory=list)
    documents: list[DocumentReference] = Field(default_factory=list)