import asyncio
import logging
import os
import time
from threading import Lock

import httpx
from dotenv import load_dotenv
from tavily import AsyncTavilyClient
from tavily.errors import UsageLimitExceededError

from backend.models.research import SearchResult


load_dotenv()

logger = logging.getLogger("agentlab")
SEARCH_CACHE_TTL_SECONDS = 300
SEARCH_CACHE_MAX_ENTRIES = 256
_search_cache: dict[str, tuple[float, list[SearchResult]]] = {}
_search_cache_lock = Lock()


def _cached_results(query: str) -> list[SearchResult] | None:
    key = query.strip().casefold()
    now = time.monotonic()
    with _search_cache_lock:
        cached = _search_cache.get(key)
        if cached is None:
            return None
        expires_at, results = cached
        if expires_at <= now:
            _search_cache.pop(key, None)
            return None
        return list(results)


def _cache_results(query: str, results: list[SearchResult]) -> None:
    key = query.strip().casefold()
    with _search_cache_lock:
        expired = [
            cache_key
            for cache_key, (expires_at, _) in _search_cache.items()
            if expires_at <= time.monotonic()
        ]
        for cache_key in expired:
            _search_cache.pop(cache_key, None)
        if len(_search_cache) >= SEARCH_CACHE_MAX_ENTRIES:
            oldest_key = min(_search_cache, key=lambda item: _search_cache[item][0])
            _search_cache.pop(oldest_key, None)
        _search_cache[key] = (
            time.monotonic() + SEARCH_CACHE_TTL_SECONDS,
            list(results),
        )


async def search_web_async(query: str) -> list[SearchResult]:
    if not os.getenv("TAVILY_API_KEY"):
        raise RuntimeError("TAVILY_API_KEY is not configured")

    cached = _cached_results(query)
    if cached is not None:
        logger.info("search_cache status=hit query_chars=%d", len(query))
        return cached

    api_key = os.getenv("TAVILY_API_KEY")
    started = time.perf_counter()
    async with httpx.AsyncClient(timeout=20.0) as http_client:
        client = AsyncTavilyClient(api_key=api_key, client=http_client)
        for attempt in range(3):
            try:
                response = await client.search(
                    query=query,
                    max_results=5,
                    timeout=20,
                )
                break
            except Exception as error:
                status = getattr(error, "status_code", None)
                response_obj = getattr(error, "response", None)
                status = status or getattr(response_obj, "status_code", None)
                is_retryable = isinstance(error, UsageLimitExceededError) or status == 429 or (
                    isinstance(status, int) and 500 <= status <= 599
                )
                if not is_retryable or attempt == 2:
                    raise
                await asyncio.sleep(min(0.25 * (2**attempt), 1.0))
        else:  # pragma: no cover - loop either breaks or raises.
            raise RuntimeError("Tavily search failed without returning a response.")

    results = [
        SearchResult(
            title=result["title"],
            url=result["url"],
            content=result["content"],
            score=result["score"],
        )
        for result in response["results"]
    ]
    _cache_results(query, results)
    logger.info(
        "search query_chars=%d results=%d seconds=%.2f status=ok",
        len(query),
        len(results),
        time.perf_counter() - started,
    )
    return results


def search_web(query: str) -> list[SearchResult]:
    """Synchronous compatibility wrapper around the async Tavily client."""
    return asyncio.run(search_web_async(query))
