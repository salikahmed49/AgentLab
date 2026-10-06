from backend.models.research import SearchResult
from backend.services.llm import generate_response
from backend.services.source_context import format_sources


class VerificationAgent:

    def run(
        self,
        topic: str,
        research: str,
        analysis: str,
        sources: list[SearchResult],
        document_context: str = "",
    ) -> str:

        source_context = format_sources(sources)

        document_block = ""
        if document_context.strip():
            document_block = f"""

User-provided document context:
{document_context[:4000]}
"""

        prompt = f"""
Topic:
{topic}

Research:
{research[:4000]}

Analysis:
{analysis[:4000]}

Original sources:
{source_context}
{document_block}

Verify the important claims made in the research and analysis.

For each important claim:

1. State the claim.
2. Mark it as:
   - SUPPORTED
   - PARTIALLY SUPPORTED
   - NOT SUPPORTED
   - CONFLICTING
3. Explain why.
4. Reference the relevant source number(s).

Rules:
- Do not invent evidence.
- If evidence is insufficient, say so.
- Identify contradictions.
- Use the supplied documents as supporting context only when they are consistent with the sources.
- Do not treat unsupported claims as facts.
"""

        return generate_response(
            prompt,
            system_prompt=(
                "You are the Verification Agent in a multi-agent research system. "
                "Check whether important claims are supported by the supplied evidence."
            )
        )