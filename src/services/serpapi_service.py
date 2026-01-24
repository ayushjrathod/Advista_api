from serpapi import GoogleSearch
from src.utils.config import settings
import asyncio
from concurrent.futures import ThreadPoolExecutor

# Thread pool for running blocking SerpAPI calls
executor = ThreadPoolExecutor(max_workers=5)

class SerpApiService:
    def search(self, query: str, query_type: str) -> dict:
        """
        Run a single SerpAPI search (blocking).
        """
        serp_params = {
            "api_key": settings.SERPAPI_API_KEY,
            "engine": "google",
            "q": query,
            "output": "json",
        }
        search = GoogleSearch(serp_params)
        results = search.get_dict()
        return {"query_type": query_type, "query": query, "results": results}

async def run_serp_search_async(query: str, query_type: str) -> dict:
    """
    Run SerpAPI search asynchronously using thread pool executor.
    """
    loop = asyncio.get_event_loop()
    service = SerpApiService()
    return await loop.run_in_executor(executor, service.search, query, query_type)

