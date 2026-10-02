from langgraph.graph import END, START, StateGraph

from backend.agents.analysis_agent import AnalysisAgent
from backend.agents.report_agent import ReportAgent
from backend.agents.research_agent import ResearchAgent
from backend.agents.verification_agent import VerificationAgent
from backend.models.state import ResearchState


research_agent = ResearchAgent()
analysis_agent = AnalysisAgent()
verification_agent = VerificationAgent()
report_agent = ReportAgent()


def research_node(state: ResearchState):
    result = research_agent.run(state["topic"])

    return {
        "research": result["research"],
        "sources": result["sources"],
    }


def analysis_node(state: ResearchState):
    analysis = analysis_agent.run(
        topic=state["topic"],
        research=state["research"],
        sources=state["sources"],
    )

    return {
        "analysis": analysis,
    }


def verification_node(state: ResearchState):
    verification = verification_agent.run(
        topic=state["topic"],
        research=state["research"],
        analysis=state["analysis"],
        sources=state["sources"],
    )

    return {
        "verification": verification,
    }


def report_node(state: ResearchState):
    report = report_agent.run(
        topic=state["topic"],
        research=state["research"],
        analysis=state["analysis"],
        verification=state["verification"],
        sources=state["sources"],
    )

    return {
        "report": report,
    }


graph_builder = StateGraph(ResearchState)

graph_builder.add_node("research", research_node)
graph_builder.add_node("analysis", analysis_node)
graph_builder.add_node("verification", verification_node)
graph_builder.add_node("report", report_node)

graph_builder.add_edge(START, "research")
graph_builder.add_edge("research", "analysis")
graph_builder.add_edge("analysis", "verification")
graph_builder.add_edge("verification", "report")
graph_builder.add_edge("report", END)

research_graph = graph_builder.compile()