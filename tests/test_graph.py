from threading import Barrier

from backend.graph import research_graph


def test_citation_and_follow_up_agents_run_in_parallel(monkeypatch):
    agents_started_together = Barrier(2)
    completed_results = []

    class FakeResearchAgent:
        def run(self, topic, document_context=""):
            return {"research": "Research notes", "sources": []}

    class FakeAnalysisAgent:
        def run(self, **kwargs):
            return "Analysis notes"

    class FakeVerificationAgent:
        def run(self, **kwargs):
            return "Verification notes"

    class FakeReportAgent:
        def run(self, **kwargs):
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
