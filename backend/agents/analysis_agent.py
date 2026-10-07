import asyncio
import json
import logging

from backend.models.research import SearchResult
from backend.services.llm import agenerate_response
from backend.services.source_context import format_sources


logger = logging.getLogger("agentlab")


class AnalysisAgent:

    def run(
        self,
        topic: str,
        research: str,
        sources: list[SearchResult],
        document_context: str = "",
    ) -> str:
        return asyncio.run(
            self.arun(topic, research, sources, document_context)
        )

    async def arun(
        self,
        topic: str,
        research: str,
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

Research Agent output:
{research}

Original sources:
{source_context}
{document_block}

Analyze all supplied sources together. Return one JSON object with concise
string-array values for these keys: key_findings, patterns_and_trends,
benefits, limitations_and_risks, disagreements, observations, and evidence_gaps.

Do not introduce facts that are not supported by the research, document context, or sources.

The goal is to understand the research, not simply repeat it.
"""

        response = await agenerate_response(
            prompt,
            system_prompt=(
                "You are the Analysis Agent in a multi-agent research system. "
                "You interpret research, identify patterns, compare information, "
                "and explain what the collected evidence means."
            ),
            stage="analysis",
            response_format="json",
            max_output_tokens=1500,
        )
        try:
            analysis = json.loads(response)
        except json.JSONDecodeError:
            logger.warning("analysis_json_parse_failed; retaining provider response")
            return response
        if not isinstance(analysis, dict):
            logger.warning("analysis_json_shape_invalid; retaining provider response")
            return response

        labels = {
            "key_findings": "Key findings",
            "patterns_and_trends": "Patterns and trends",
            "benefits": "Benefits",
            "limitations_and_risks": "Limitations and risks",
            "disagreements": "Disagreements between sources",
            "observations": "Important observations",
            "evidence_gaps": "Evidence gaps",
        }
        sections = []
        for key, label in labels.items():
            values = analysis.get(key, [])
            if isinstance(values, str):
                values = [values]
            if isinstance(values, list) and values:
                sections.append(
                    f"## {label}\n"
                    + "\n".join(f"- {item}" for item in values if isinstance(item, str))
                )
        return "\n\n".join(sections) if sections else response