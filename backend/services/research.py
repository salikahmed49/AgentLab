import logging
import time

from backend.graph import research_graph
from backend.models.research import DocumentReference


logger = logging.getLogger("agentlab")


def _build_document_context(documents: list[DocumentReference]) -> str:
    if not documents:
        return ""

    chunks = []
    for document in documents:
        text = (document.content or "").strip()
        if not text:
            continue
        chunks.append(f"Document: {document.name}\n\n{text[:4000]}")
    return "\n\n---\n\n".join(chunks)


def perform_research(
    topic: str,
    documents: list[DocumentReference] | None = None,
    on_step=None,
    on_result=None,
    on_report_chunk=None,
) -> dict:
    started = time.perf_counter()
    doc_list = documents or []
    document_context = _build_document_context(doc_list)

    try:
        result = research_graph.invoke(
            {
                "topic": topic,
                "research": "",
                "analysis": "",
                "verification": "",
                "report": "",
                "sources": [],
                "document_context": document_context,
                "documents": [item.name for item in doc_list],
                "on_step": on_step,
                "on_result": on_result,
                "on_report_chunk": on_report_chunk,
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
            "citations": result.get("citations", []),
            "follow_up_questions": result.get("follow_up_questions", []),
            "documents": doc_list,
        }
    finally:
        logger.info("total request took %.2f s", time.perf_counter() - started)