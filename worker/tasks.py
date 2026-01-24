import random
import time
from worker.celery_app import celery_app
from src.services.serpapi_service import SerpApiService

@celery_app.task(name = "process_data")
def process_data(data: int):
    # simulate a data processing task
    time.sleep(5)  # simulate a time-consuming task
    return {
        "status": "completed",
        "data_id": data,
        "result": f"Data {data} processed successfully"
    }

@celery_app.task(name="serpapi_search")
def serpapi_search(query: str, search_type: str = "general"):
    """
    Execute a SerpAPI search for a given query and type.
    """
    try:
        service = SerpApiService()
        results = service.search(query, search_type)
        return results
    except Exception as e:
        return {"error": str(e), "query": query, "type": search_type}

