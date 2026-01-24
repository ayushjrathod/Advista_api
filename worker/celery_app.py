import os
from celery import Celery

#commands to run 
# docker run -p 6379:6379 -d redis
# uv run celery -A worker.celery_app.celery_app worker --loglevel=info
# we can also run a web based monitor for celery called flower in uvx
# uvx flower --port=5555 --broker=redis://localhost:6379/0
# we can then access the flower monitor at http://localhost:5555

REDIS_URL = os.getenv('REDIS_URL', 'redis://localhost:6379/0')

celery_app = Celery(
  "worker",
  broker = REDIS_URL,
  backend = REDIS_URL,
  # Ensure task modules are imported so the worker registers tasks like `process_data`
  include=["worker.tasks"],
)

celery_app.conf.update(
    task_serializer = 'json',
    result_serializer = 'json',
    accept_content = ['json'],
    timezone = 'UTC',
    enable_utc = True,
)
