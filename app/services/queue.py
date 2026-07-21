from celery import Celery

from app.config import get_settings

settings = get_settings()

celery_app = Celery(
    "media_pipeline",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_default_queue="image_processing",
    task_routes={"app.workers.tasks.process_image": {"queue": "image_processing"}},
    task_autoretry_for=(Exception,),
    task_retry_kwargs={"max_retries": 3, "countdown": 5},
    task_retry_backoff=True,
    task_retry_backoff_max=60,
)

celery_app.autodiscover_tasks(["app.workers"])
