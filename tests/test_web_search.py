import asyncio

from backend.tools import web_search


def test_search_uses_async_tavily_and_caches_repeated_queries(monkeypatch):
    calls = []

    class FakeHTTPClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

    class FakeTavilyClient:
        def __init__(self, api_key, client):
            assert api_key == "test-key"
            assert isinstance(client, FakeHTTPClient)

        async def search(self, **options):
            calls.append(options)
            return {
                "results": [
                    {
                        "title": "Cached result",
                        "url": "https://example.com",
                        "content": "Evidence snippet",
                        "score": 0.9,
                    }
                ]
            }

    monkeypatch.setenv("TAVILY_API_KEY", "test-key")
    monkeypatch.setattr(web_search, "_search_cache", {})
    monkeypatch.setattr(web_search.httpx, "AsyncClient", lambda **_: FakeHTTPClient())
    monkeypatch.setattr(web_search, "AsyncTavilyClient", FakeTavilyClient)

    first = asyncio.run(web_search.search_web_async("  Battery research "))
    second = asyncio.run(web_search.search_web_async("battery research"))

    assert first == second
    assert first[0].title == "Cached result"
    assert len(calls) == 1
    assert calls[0]["max_results"] == 5
