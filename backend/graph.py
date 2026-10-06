from langgraph.graph import END, START, StateGraph

from backend.agents.analysis_agent import AnalysisAgent
from backend.agents.citation_agent import CitationAgent
from backend.agents.follow_up_question_agent import FollowUpQuestionAgent
from backend.agents.report_agent import ReportAgent
from backend.agents.research_agent import ResearchAgent
from backend.agents.verification_agent import VerificationAgent
from backend.models.state import ResearchState
from backend.services.harness import run_step


research_agent = ResearchAgent()
analysis_agent = AnalysisAgent()
verification_agent = VerificationAgent()
report_agent = ReportAgent()
citation_agent = CitationAgent()
follow_up_question_agent = FollowUpQuestionAgent()


def research_node(state: ResearchState):
    result = run_step(
        "research",
        lambda: research_agent.run(
            state["topic"],
            document_context=state.get("document_context", ""),
        ),
        on_step=state.get("on_step"),
        on_result=state.get("on_result"),
    )

    return {
        "research": result["research"],
        "sources": result["sources"],
    }


def analysis_node(state: ResearchState):
    analysis = run_step(
        "analysis",
        lambda: analysis_agent.run(
            topic=state["topic"],
            research=state["research"],
            sources=state["sources"],
            document_context=state.get("document_context", ""),
        ),
        on_step=state.get("on_step"),
        on_result=state.get("on_result"),
    )

    return {
        "analysis": analysis,
    }


def verification_node(state: ResearchState):
    verification = run_step(
        "verification",
        lambda: verification_agent.run(
            topic=state["topic"],
            research=state["research"],
            analysis=state["analysis"],
            sources=state["sources"],
            document_context=state.get("document_context", ""),
        ),
        on_step=state.get("on_step"),
        on_result=state.get("on_result"),
    )

    return {
        "verification": verification,
    }


def report_node(state: ResearchState):
    report = run_step(
        "report",
        lambda: report_agent.run(
            topic=state["topic"],
            research=state["research"],
            analysis=state["analysis"],
            verification=state["verification"],
            sources=state["sources"],
            document_context=state.get("document_context", ""),
        ),
        on_step=state.get("on_step"),
        on_result=state.get("on_result"),
    )

    return {
        "report": report,
    }


def citation_node(state: ResearchState):
    citations = run_step(
        "citation_linking",
        lambda: citation_agent.run(
            topic=state["topic"],
            report=state["report"],
            verification=state["verification"],
            sources=state["sources"],
            document_context=state.get("document_context", ""),
        ),
        on_step=state.get("on_step"),
        on_result=state.get("on_result"),
    )

    return {
        "citations": citations,
    }


def follow_up_node(state: ResearchState):
    questions = run_step(
        "follow_up_questions",
        lambda: follow_up_question_agent.run(
            topic=state["topic"],
            report=state["report"],
            analysis=state["analysis"],
            verification=state["verification"],
            sources=state["sources"],
        ),
        on_step=state.get("on_step"),
        on_result=state.get("on_result"),
    )

    return {
        "follow_up_questions": questions,
    }


graph_builder = StateGraph(ResearchState)

graph_builder.add_node("research", research_node)
graph_builder.add_node("analysis", analysis_node)
graph_builder.add_node("verification", verification_node)
graph_builder.add_node("report", report_node)
graph_builder.add_node("citation_linking", citation_node)
graph_builder.add_node("follow_up_questions", follow_up_node)

graph_builder.add_edge(START, "research")
graph_builder.add_edge("research", "analysis")
graph_builder.add_edge("analysis", "verification")
graph_builder.add_edge("verification", "report")
graph_builder.add_edge("report", "citation_linking")
graph_builder.add_edge("report", "follow_up_questions")
graph_builder.add_edge("follow_up_questions", END)
graph_builder.add_edge("citation_linking", END)

research_graph = graph_builder.compile()
