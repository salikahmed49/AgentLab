import asyncio

from backend.agents import analysis_agent
from backend.agents.analysis_agent import AnalysisAgent
from backend.models.research import SearchResult


def test_analysis_falls_back_to_grounded_output_when_providers_fail(monkeypatch):
    async def unavailable_provider(*args, **kwargs):
        raise RuntimeError("Groq and Gemini are unavailable")

    monkeypatch.setattr(
        analysis_agent, "agenerate_response", unavailable_provider
    )

    result = asyncio.run(
        AnalysisAgent().arun(
            topic="Battery recycling",
            research="Recovery rates vary by battery chemistry.",
            sources=[
                SearchResult(
                    title="Battery study",
                    url="https://example.com/study",
                    content="The study measured recovery rates by chemistry.",
                    score=0.9,
                )
            ],
        )
    )

    assert "## Key findings" in result
    assert "Recovery rates vary by battery chemistry." in result
    assert "Battery study" in result
    assert "## Evidence gaps" in result


def test_analysis_fallback_handles_no_available_evidence(monkeypatch):
    async def unavailable_provider(*args, **kwargs):
        raise RuntimeError("No providers configured")

    monkeypatch.setattr(
        analysis_agent, "agenerate_response", unavailable_provider
    )

    result = asyncio.run(
        AnalysisAgent().arun(
            topic="Nanoplastics",
            research="",
            sources=[],
        )
    )

    assert "No usable research" in result
    assert "## Patterns and trends" in result
    assert "## Limitations and risks" in result
