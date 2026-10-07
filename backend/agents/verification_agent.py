import asyncio
import json
import logging

from backend.models.research import SearchResult
from backend.services.llm import agenerate_response
from backend.services.source_context import format_sources


logger = logging.getLogger("agentlab")


class VerificationAgent:

    def run(
        self,
        topic: str,
        research: str,
        analysis: str,
        sources: list[SearchResult],
        document_context: str = "",
    ) -> str:
        return asyncio.run(
            self.arun(topic, research, analysis, sources, document_context)
        )

    async def arun(
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

Verify all important claims in one pass. Return a JSON object with a "claims"
array. Each array item has claim, verdict, explanation, and source_numbers fields.
Allowed verdicts are SUPPORTED, PARTIALLY SUPPORTED, NOT SUPPORTED, and CONFLICTING.

Rules:
- Do not invent evidence.
- If evidence is insufficient, say so.
- Identify contradictions.
- Use the supplied documents as supporting context only when they are consistent with the sources.
- Do not treat unsupported claims as facts.
"""

        response = await agenerate_response(
            prompt,
            system_prompt=(
                "You are the Verification Agent in a multi-agent research system. "
                "Check whether important claims are supported by the supplied evidence."
            ),
            stage="verification",
            response_format="json",
            max_output_tokens=1600,
        )
        try:
            claims = json.loads(response)
        except json.JSONDecodeError:
            logger.warning("verification_json_parse_failed; retaining provider response")
            return response
        if isinstance(claims, dict):
            claims = claims.get("claims")
        if not isinstance(claims, list):
            logger.warning("verification_json_shape_invalid; retaining provider response")
            return response

        formatted = []
        for claim in claims:
            if not isinstance(claim, dict):
                continue
            statement = claim.get("claim", "Claim")
            verdict = claim.get("verdict", "PARTIALLY SUPPORTED")
            explanation = claim.get("explanation", "")
            source_numbers = claim.get("source_numbers", [])
            references = (
                ", ".join(str(number) for number in source_numbers)
                if isinstance(source_numbers, list)
                else str(source_numbers)
            )
            formatted.append(
                f"- **{verdict}:** {statement} {explanation}"
                + (f" (Sources: {references})" if references else "")
            )
        return "\n".join(formatted) if formatted else response