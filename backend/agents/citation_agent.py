import asyncio
import json
import logging

from backend.models.research import SearchResult
from backend.services.llm import agenerate_response, LLMProviderError
from backend.services.source_context import format_sources


logger = logging.getLogger("agentlab")


class CitationAgent:

    def run(
        self,
        topic: str,
        report: str,
        verification: str,
        sources: list[SearchResult],
        document_context: str = "",
    ) -> list[dict]:
        return asyncio.run(
            self.arun(topic, report, verification, sources, document_context)
        )

    async def arun(
        self,
        topic: str,
        report: str,
        verification: str,
        sources: list[SearchResult],
        document_context: str = "",
    ) -> list[dict]:
        source_context = format_sources(sources)

        document_block = ""
        if document_context.strip():
            document_block = f"""

User-provided document context:
{document_context[:3000]}
"""

        prompt = f"""
Topic:
{topic}

Final report:
{report[:4000]}

Verification notes:
{verification[:4000]}

Sources:
{source_context}
{document_block}

Create a short, evidence-linked citation list for the most important claims in the report.
Return a JSON object with a "citations" array. Each item has claim,
source_title, source_url, and quote fields.

Rules:
- Use only the provided sources and document context.
- Include at most 3 citations.
- Use exact source titles and URLs from the supplied materials.
- Keep the quote short and factual.
"""

        try:
            response = await agenerate_response(
                prompt,
                system_prompt=(
                    "You are the Citation and Evidence Linker Agent. "
                    "Return only a JSON object whose citations array connects major claims to exact sources."
                ),
                stage="citation_linking",
                response_format="json",
                max_output_tokens=500,
            )
        except LLMProviderError:
            logger.exception("citation_generation_failed; using source-grounded fallback")
            response = ""

        try:
            parsed = json.loads(response)
            if isinstance(parsed, list):
                return parsed
            if isinstance(parsed, dict):
                return parsed.get("citations", [])
        except (TypeError, ValueError) as error:
            logger.warning("citation_json_parse_failed: %s", type(error).__name__)

        if not sources:
            return []

        primary = sources[0]
        return [{
            "claim": "The report is grounded in the most relevant source material.",
            "source_title": primary.title,
            "source_url": primary.url,
            "quote": primary.content[:220],
        }]
