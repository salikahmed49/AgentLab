from backend.models.research import SearchResult


def format_sources(results: list[SearchResult]) -> str:
    formatted_sources = []

    for index, result in enumerate(results, start=1):
        content = result.content[:1000]

        formatted_sources.append(
            f"""
[Source {index}]
Title: {result.title}
URL: {result.url}

Content:
{content}
"""
        )

    return "\n".join(formatted_sources)