import asyncio

from backend.models.research import SearchResult
from backend.services.llm import agenerate_response
from backend.tools.web_search import search_web_async


class ResearchAgent:

    def run(self, topic: str, document_context: str = "") -> dict:
        return asyncio.run(self.arun(topic, document_context))

    async def arun(self, topic: str, document_context: str = "") -> dict:
        results: list[SearchResult] = await search_web_async(topic)

        research_context = "\n\n".join(
            [
                f"""
Title: {result.title}
URL: {result.url}
Content:
{result.content[:800]}
"""
                for result in results
            ]
        )

        document_block = ""
        if document_context.strip():
            document_block = f"""

User-provided documents:
{document_context}
"""

        prompt = f"""
Research topic:
{topic}

The following information was collected from web search:

{research_context}
{document_block}

Create a factual research summary based only on the supplied information.

Requirements:
- Explain the main concepts.
- Identify important findings.
- Combine information across sources.
- Use the user-provided documents as supporting context when relevant.
- Do not invent facts.
- Clearly distinguish facts from uncertainty.
- Keep the research useful for a later analysis agent.
"""

        research = await agenerate_response(
            prompt,
            system_prompt=(
                "You are the Research Agent in a multi-agent research system. "
                "Your job is to collect and synthesize factual information "
                "from the supplied web sources."
            ),
            stage="research",
            max_output_tokens=1400,
        )

        return {
            "research": research,
            "sources": results
        }