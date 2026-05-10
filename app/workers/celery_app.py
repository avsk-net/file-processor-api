# app/workers/celery_app.py
from celery import Celery
from app.core.config import settings

celery_app = Celery(
    "file_processor",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL.replace("/0", "/1"),
    include=["app.workers.tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_acks_late=True,
)
