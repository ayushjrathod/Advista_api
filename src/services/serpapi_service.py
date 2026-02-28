import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor
from typing import Optional

from serpapi import GoogleSearch

from src.utils.config import settings

logger = logging.getLogger(__name__)
# Thread pool for running blocking SerpAPI calls
executor = ThreadPoolExecutor(max_workers=5)


class SerpApiService:
    def search(
        self,
        query: str,
        query_type: str,
        engine: str = "google",
        *,
        device: Optional[str] = None,
        gl: Optional[str] = None,
        hl: Optional[str] = None,
        location: Optional[str] = None,
        start: Optional[int] = None,
    ) -> dict:
        """
        Run a single SerpAPI search (blocking).

        Args:
            query: Search query string
            query_type: Category/type of query (product, competitor, etc.)
            engine: SerpAPI engine - "google" (default) or "google_forums"
            device: Optional - desktop, tablet, or mobile (Forums)
            gl: Optional - country code (e.g., us, uk)
            hl: Optional - language code (e.g., en, es)
            location: Optional - geographic location for search
            start: Optional - result offset for pagination
        """
        serp_params = {
            "api_key": settings.SERPAPI_API_KEY,
            "engine": engine,
            "q": query,
            "output": "json",
        }
        if device is not None:
            serp_params["device"] = device
        if gl is not None:
            serp_params["gl"] = gl
        if hl is not None:
            serp_params["hl"] = hl
        if location is not None:
            serp_params["location"] = location
        if start is not None:
            serp_params["start"] = start

        # TODO: remove after debugging
        if engine == "google_forums":
            logger.info(f"[REDDIT/FORUMS] Starting search | query_type={query_type} | query={query[:80]}...")
        search = GoogleSearch(serp_params)
        results = search.get_dict()
        # TODO: remove after debugging
        if engine == "google_forums":
            organic = results.get("organic_results", [])
            logger.info(f"[REDDIT/FORUMS] Search complete | query_type={query_type} | organic_results={len(organic)} | status={results.get('search_metadata', {}).get('status')}")
            for i, r in enumerate(organic[:3]):
                logger.info(f"[REDDIT/FORUMS]   result[{i+1}] title={r.get('title', '')[:50]}... | source={r.get('source', '')}")
        return {"query_type": query_type, "query": query, "results": results}

    def search_youtube(self, search_query: str) -> dict:
        """
        Run YouTube search via SerpAPI.
        Returns video_results and shorts_results from the API response.
        """
        # TODO: remove after debugging
        logger.info(f"[YT] SerpAPI search starting | search_query={search_query[:80]}...")
        serp_params = {
            "api_key": settings.SERPAPI_API_KEY,
            "engine": "youtube",
            "search_query": search_query,
            "output": "json",
        }
        search = GoogleSearch(serp_params)
        results = search.get_dict()
        # TODO: remove after debugging
        vcount = len(results.get("video_results", []))
        scount = len(results.get("shorts_results", []))
        logger.info(f"[YT] SerpAPI search complete | videos={vcount} | shorts_sections={scount} | error={results.get('error', 'none')}")
        return results


async def run_serp_search_async(
    query: str,
    query_type: str,
    engine: str = "google",
    **kwargs,
) -> dict:
    """
    Run SerpAPI search asynchronously using thread pool executor.

    Args:
        query: Search query string
        query_type: Category/type of query
        engine: "google" (default) or "google_forums"
        **kwargs: Optional Forums params (device, gl, hl, location, start)
    """
    loop = asyncio.get_running_loop()
    service = SerpApiService()
    return await loop.run_in_executor(
        executor,
        lambda: service.search(query, query_type, engine, **kwargs),
    )

