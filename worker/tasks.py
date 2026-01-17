import time
from worker.celery_app import celery_app

@celery_app.task(name = "process_data")
def process_data(data_id: int):
    # simulate a data processing task
    time.sleep(5)  # simulate a time-consuming task
    return {
        "status": "completed",
        "data_id": data_id,
        "result": f"Data {data_id} processed successfully"
    }
