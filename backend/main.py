from fastapi import FastAPI

from backend.models.research import ResearchRequest, ResearchResponse
from backend.services.research import perform_research


app = FastAPI()


@app.get("/")
def home():
    return {"message": "AgentLab API is running"}


@app.get("/health")
def health():
    return {"status": "healthy"}


@app.post("/research", response_model=ResearchResponse)
def research(request: ResearchRequest):
    return perform_research(request.topic)