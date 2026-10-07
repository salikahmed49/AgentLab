import asyncio

from backend.agents import verification_agent
from backend.agents.verification_agent import VerificationAgent
from backend.models.research import SearchResult


def test_verification_falls_back_to_explicit_unverified_evidence(monkeypatch):
    async def unavailable_provider(*args, **kwargs):
        raise RuntimeError("Groq and Gemini rate limited")

    monkeypatch.setattr(
        verification_agent, "agenerate_response", unavailable_provider
    )

    result = asyncio.run(
        VerificationAgent().arun(
            topic="Battery recycling",
            research="Recovery rates differ by chemistry.",
            analysis="## Key finding\n- Recovery rates differ by chemistry.",
            sources=[
                SearchResult(
                    title="Battery study",
                    url="https://example.com/study",
                    content="Recovery rates were measured for three chemistries.",
                    score=0.9,
                )
            ],
        )
    )

    assert "could not be completed" in result
    assert "none of it has been independently verified" in result
    assert "Battery study" in result
    assert "Recovery rates differ by chemistry." in result


def test_verification_fallback_handles_missing_evidence(monkeypatch):
    async def unavailable_provider(*args, **kwargs):
        raise RuntimeError("No verification provider available")

    monkeypatch.setattr(
        verification_agent, "agenerate_response", unavailable_provider
    )

    result = asyncio.run(
        VerificationAgent().arun(
            topic="Nanoplastics",
            research="",
            analysis="",
            sources=[],
        )
    )

    assert "no usable evidence" in result
    assert "Treat all claims as unverified" in result
