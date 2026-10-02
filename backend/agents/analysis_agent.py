from backend.models.research import SearchResult
from backend.services.llm import generate_response
from backend.services.source_context import format_sources


class AnalysisAgent:

    def run(
        self,
        topic: str,
        research: str,
        sources: list[SearchResult]
    ) -> str:

        source_context = format_sources(sources)

        prompt = f"""
Topic:
{topic}

Research Agent output:
{research}

Original sources:
{source_context}

Analyze the research.

Your analysis should include:

1. Key findings
2. Major patterns or trends
3. Benefits or positive findings
4. Limitations or risks
5. Important disagreements between sources
6. Important observations
7. Areas where evidence is weak or incomplete

Do not introduce facts that are not supported by the research or sources.

The goal is to understand the research, not simply repeat it.
"""

        return generate_response(
            prompt,
            system_prompt=(
                "You are the Analysis Agent in a multi-agent research system. "
                "You interpret research, identify patterns, compare information, "
                "and explain what the collected evidence means."
            )
        )