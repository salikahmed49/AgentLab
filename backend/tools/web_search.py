import os

from dotenv import load_dotenv
from tavily import TavilyClient

from backend.models.research import SearchResult


load_dotenv()


def search_web(query: str) -> list[SearchResult]:
    api_key = os.getenv("TAVILY_API_KEY")

    if not api_key:
        raise RuntimeError("TAVILY_API_KEY is not configured")

    client = TavilyClient(api_key=api_key)

    response = client.search(
        query=query,
        max_results=5
    )

    results = []

    for result in response["results"]:
        results.append(
            SearchResult(
                title=result["title"],
                url=result["url"],
                content=result["content"],
                score=result["score"]
            )
        )

    return results