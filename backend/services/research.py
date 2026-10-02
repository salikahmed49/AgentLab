from backend.graph import research_graph


def perform_research(topic: str) -> dict:
    result = research_graph.invoke(
        {
            "topic": topic,
            "research": "",
            "analysis": "",
            "verification": "",
            "report": "",
            "sources": [],
        }
    )

    return {
        "topic": result["topic"],
        "status": "completed",
        "research": result["research"],
        "analysis": result["analysis"],
        "verification": result["verification"],
        "report": result["report"],
        "sources": result["sources"],
    }