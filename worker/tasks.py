"""
Celery tasks. Define serpapi_search, process_data, etc. here.
"""
from worker.celery_app import celery_app


@celery_app.task(name="process_data")
def process_data(data: dict):
    """Placeholder task. Replace with your implementation."""
    return {"status": "ok", "data": data}


@celery_app.task(name="serpapi_search")
def serpapi_search(query: str, query_type: str, engine: str):
    """Placeholder for SerpAPI search task. Wire to your serpapi_service."""
    return {"status": "pending", "query": query, "query_type": query_type, "engine": engine}
