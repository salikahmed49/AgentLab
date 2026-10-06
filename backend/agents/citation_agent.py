import json

from backend.models.research import SearchResult
from backend.services.llm import generate_response
from backend.services.source_context import format_sources


class CitationAgent:

    def run(
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
Return valid JSON in this exact shape:
[
  {{
    "claim": "Short claim summary",
    "source_title": "Source title",
    "source_url": "https://example.com",
    "quote": "Short quote from the source"
  }}
]

Rules:
- Use only the provided sources and document context.
- Include at most 3 citations.
- Use exact source titles and URLs from the supplied materials.
- Keep the quote short and factual.
"""

        try:
            response = generate_response(
                prompt,
                system_prompt=(
                    "You are the Citation and Evidence Linker Agent. "
                    "Return only valid JSON array objects that connect major claims to exact sources."
                )
            )
        except Exception:
            response = ""

        try:
            parsed = json.loads(response)
            if isinstance(parsed, list):
                return parsed
            if isinstance(parsed, dict):
                return parsed.get("citations", [])
        except (TypeError, ValueError):
            pass

        if not sources:
            return []

        primary = sources[0]
        return [{
            "claim": "The report is grounded in the most relevant source material.",
            "source_title": primary.title,
            "source_url": primary.url,
            "quote": primary.content[:220],
        }]
