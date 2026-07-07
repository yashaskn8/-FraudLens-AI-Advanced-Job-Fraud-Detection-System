"""
Celery application configuration.
"""
from celery import Celery
from backend.config import settings

celery_app = Celery(
    "trusthire",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=120,
    task_soft_time_limit=90,
    worker_max_tasks_per_child=100,
)

celery_app.autodiscover_tasks(["backend.tasks"])
