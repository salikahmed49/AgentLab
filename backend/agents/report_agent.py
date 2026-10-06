from backend.models.research import SearchResult
from backend.services.llm import generate_response
from backend.services.source_context import format_sources


class ReportAgent:

    def run(
        self,
        topic: str,
        research: str,
        analysis: str,
        verification: str,
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
{research[:4500]}

Analysis:
{analysis[:4500]}

Verification:
{verification[:4500]}

Sources:
{source_context}
{document_block}

Write the final research report.

Use this structure:

# {topic}

## Executive Summary

## Key Findings

## Analysis

## Verified Findings

## Limitations and Uncertainty

## Conclusion

## Sources

For Sources, list the supplied source titles and URLs.

Requirements:
- Use the supplied research, verification, and uploaded document context when it adds signal.
- Do not invent facts.
- Clearly identify uncertainty.
- Do not present unsupported claims as established facts.
- Be professional and concise.
"""

        return generate_response(
            prompt,
            system_prompt=(
                "You are the Report Agent in a multi-agent research system. "
                "Turn researched, analyzed, and verified information into a professional report."
            )
        )