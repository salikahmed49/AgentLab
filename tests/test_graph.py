import asyncio
from threading import Barrier

from backend.agents.report_agent import REPORT_SECTIONS, ReportAgent
from backend.graph import research_graph
from backend.services import llm as llm_module


def test_citation_and_follow_up_agents_run_in_parallel(monkeypatch):
    agents_started_together = Barrier(2)
    completed_results = []
    report_sections = []

    class FakeResearchAgent:
        def run(self, topic, document_context=""):
            return {"research": "Research notes", "sources": []}

    class FakeAnalysisAgent:
        def run(
            self,
            *,
            topic,
            research,
            sources,
            document_context="",
        ):
            return "Analysis notes"

    class FakeVerificationAgent:
        def run(self, **kwargs):
            return "Verification notes"

    class FakeReportAgent:
        def run(self, *, on_section=None, **kwargs):
            if on_section:
                on_section(0, "Executive Summary", "A streamed summary.")
            return "Final report"

    class FakeCitationAgent:
        def run(self, **kwargs):
            agents_started_together.wait(timeout=2)
            return []

    class FakeFollowUpQuestionAgent:
        def run(self, **kwargs):
            agents_started_together.wait(timeout=2)
            return ["What should be researched next?"]

    monkeypatch.setattr("backend.graph.research_agent", FakeResearchAgent())
    monkeypatch.setattr("backend.graph.analysis_agent", FakeAnalysisAgent())
    monkeypatch.setattr("backend.graph.verification_agent", FakeVerificationAgent())
    monkeypatch.setattr("backend.graph.report_agent", FakeReportAgent())
    monkeypatch.setattr("backend.graph.citation_agent", FakeCitationAgent())
    monkeypatch.setattr(
        "backend.graph.follow_up_question_agent", FakeFollowUpQuestionAgent()
    )

    result = research_graph.invoke(
        {
            "topic": "Test topic",
            "research": "",
            "analysis": "",
            "verification": "",
            "report": "",
            "sources": [],
            "citations": [],
            "follow_up_questions": [],
            "document_context": "",
            "documents": [],
            "on_result": lambda step, value: completed_results.append(step),
            "on_report_chunk": lambda index, section, text: report_sections.append(
                (index, section, text)
            ),
        }
    )

    assert result["citations"] == []
    assert result["follow_up_questions"] == ["What should be researched next?"]
    assert set(completed_results) == {
        "research",
        "analysis",
        "verification",
        "report",
        "citation_linking",
        "follow_up_questions",
    }
    assert report_sections == [(0, "Executive Summary", "A streamed summary.")]


def test_report_sections_generate_concurrently_and_assemble_in_order(monkeypatch):
    active_calls = 0
    maximum_active_calls = 0
    emitted_sections = []

    async def fake_generate_response(prompt, system_prompt, **options):
        nonlocal active_calls, maximum_active_calls
        async with llm_module.llm_concurrency_limit() as semaphore:
            async with semaphore:
                active_calls += 1
                maximum_active_calls = max(maximum_active_calls, active_calls)
                await asyncio.sleep(0.01)
                active_calls -= 1
        return f"Generated {options['stage']} content."

    monkeypatch.setattr(
        "backend.agents.report_agent.agenerate_response", fake_generate_response
    )
    result = asyncio.run(
        ReportAgent().arun(
            topic="Concurrency",
            research="Research",
            analysis="Analysis",
            verification="Verification",
            sources=[],
            on_section=lambda index, section, text: emitted_sections.append(
                (index, section, text)
            ),
        )
    )

    assert 1 < maximum_active_calls <= 5
    assert sorted(index for index, _, _ in emitted_sections) == list(
        range(len(REPORT_SECTIONS))
    )
    assert result.index("## Executive Summary") < result.index("## Key Findings")
    assert result.index("## Key Findings") < result.index("## Analysis")


def test_report_keeps_successful_sections_when_one_generation_fails(monkeypatch):
    calls = []
    streamed = []

    async def fake_generate_response(prompt, system_prompt, **options):
        calls.append(prompt)
        if "concise executive summary" in prompt.lower():
            raise RuntimeError("simulated provider failure")
        if options.get("response_format") == "json":
            return '{"Executive Summary":"Recovered summary."}'
        return f"Generated section for {prompt[:20]}"

    monkeypatch.setattr(
        "backend.agents.report_agent.agenerate_response", fake_generate_response
    )
    report = asyncio.run(
        ReportAgent().arun(
            topic="Partial recovery",
            research="Evidence notes",
            analysis="Pattern notes",
            verification="Verified notes",
            sources=[],
            on_section=lambda index, section, text: streamed.append(
                (index, section, text)
            ),
        )
    )

    assert "## Executive Summary\n\nRecovered summary." in report
    assert "## Analysis\n\nGenerated section" in report
    assert len(calls) == len(REPORT_SECTIONS) + 1
    assert {section for _, section, _ in streamed} == {
        section for section, _ in REPORT_SECTIONS
    }


def test_report_uses_evidence_fallback_if_all_report_calls_fail(monkeypatch):
    async def fail_report_call(prompt, system_prompt, **options):
        raise RuntimeError("simulated provider outage")

    monkeypatch.setattr(
        "backend.agents.report_agent.agenerate_response", fail_report_call
    )
    report = asyncio.run(
        ReportAgent().arun(
            topic="Evidence fallback",
            research="Research evidence.",
            analysis="Analysis evidence.",
            verification="Verification evidence.",
            sources=[],
        )
    )

    assert "# Evidence fallback" in report
    assert "## Analysis\n\nAnalysis evidence." in report
    assert "## Verified Findings\n\nVerification evidence." in report
    assert "## Sources\n\nNo web sources were found." in report
