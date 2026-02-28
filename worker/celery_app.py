"""
Celery app for async background tasks.
Add task definitions here or in worker/tasks.py.
"""
import os
from celery import Celery

broker_url = os.environ.get("CELERY_BROKER_URL") or os.environ.get("REDIS_URL", "redis://localhost:6379/0")
result_backend = os.environ.get("CELERY_RESULT_BACKEND") or broker_url

celery_app = Celery(
    "advista",
    broker=broker_url,
    backend=result_backend,
    include=["worker.tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
)
