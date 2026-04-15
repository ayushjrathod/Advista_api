"""
Celery tasks for async background work.
"""
import logging

from worker.celery_app import celery_app
from src.services.serpapi_service import SerpApiService

logger = logging.getLogger(__name__)


@celery_app.task(name="process_data")
def process_data(data: dict):
    """Generic passthrough task used by /tasks/append-task for smoke testing."""
    return {"status": "ok", "data": data}


@celery_app.task(name="serpapi_search", bind=True, max_retries=2, default_retry_delay=5)
def serpapi_search(self, query: str, query_type: str, engine: str = "google"):
    """
    Run a SerpAPI search in the worker and return the raw results.

    Returns a dict shaped as {"query": ..., "results": ...} to match the
    async branch's storage in research_controller.
    """
    try:
        service = SerpApiService()
        result = service.search(query=query, query_type=query_type, engine=engine)
        return {"query": result["query"], "results": result["results"]}
    except Exception as exc:
        logger.exception(f"serpapi_search failed for {query_type}: {exc}")
        raise self.retry(exc=exc)
