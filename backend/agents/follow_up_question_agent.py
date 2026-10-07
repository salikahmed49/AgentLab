import asyncio
import json
import logging

from backend.models.research import SearchResult
from backend.services.llm import agenerate_response, LLMProviderError


logger = logging.getLogger("agentlab")


class FollowUpQuestionAgent:

    def run(
        self,
        topic: str,
        report: str,
        analysis: str,
        verification: str,
        sources: list[SearchResult],
    ) -> list[str]:
        return asyncio.run(self.arun(topic, report, analysis, verification, sources))

    async def arun(
        self,
        topic: str,
        report: str,
        analysis: str,
        verification: str,
        sources: list[SearchResult],
    ) -> list[str]:
        prompt = f"""
Topic:
{topic}

Report:
{report[:3500]}

Analysis:
{analysis[:2500]}

Verification:
{verification[:2500]}

Sources: {len(sources)} available

Generate 3 high-value follow-up questions that would deepen the research and help the user act on the findings.
Return a JSON object with a "questions" array containing three strings.
"""

        try:
            response = await agenerate_response(
                prompt,
                system_prompt=(
                    "You are the Follow-up Question Agent. "
                    "Suggest the next best questions to continue the investigation or make a decision. "
                    "Return only a JSON object with a questions array of strings."
                ),
                stage="follow_up_questions",
                response_format="json",
                max_output_tokens=250,
            )
        except LLMProviderError:
            logger.exception("follow_up_generation_failed; using deterministic questions")
            response = ""

        try:
            parsed = json.loads(response)
            if isinstance(parsed, dict):
                parsed = parsed.get("questions", [])
            if isinstance(parsed, list):
                return [str(item) for item in parsed]
        except (TypeError, ValueError) as error:
            logger.warning("follow_up_json_parse_failed: %s", type(error).__name__)

        return [
            f"What are the biggest risks or open questions around {topic}?",
            f"Which companies or actors are leading the space for {topic}?",
            f"What would you like me to compare or validate next for {topic}?",
        ]
