import json

from backend.models.research import SearchResult
from backend.services.llm import generate_response


class FollowUpQuestionAgent:

    def run(
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
Return valid JSON in this exact shape:
[
  "question 1",
  "question 2",
  "question 3"
]
"""

        try:
            response = generate_response(
                prompt,
                system_prompt=(
                    "You are the Follow-up Question Agent. "
                    "Suggest the next best questions to continue the investigation or make a decision. "
                    "Return only valid JSON array strings."
                )
            )
        except Exception:
            response = ""

        try:
            parsed = json.loads(response)
            if isinstance(parsed, list):
                return [str(item) for item in parsed]
        except (TypeError, ValueError):
            pass

        return [
            f"What are the biggest risks or open questions around {topic}?",
            f"Which companies or actors are leading the space for {topic}?",
            f"What would you like me to compare or validate next for {topic}?",
        ]
