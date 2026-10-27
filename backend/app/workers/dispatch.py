import logging
import uuid
from collections.abc import Callable

from fastapi import BackgroundTasks

from app.core.config import Settings, get_settings
from app.db.session import get_session_factory
from app.services.datasets.jobs import execute_job
from app.storage import get_storage

logger = logging.getLogger(__name__)
Enqueue = Callable[[uuid.UUID], None]


def run_job_in_new_session(job_id: uuid.UUID) -> None:
    """Entry point for both the Celery task and inline mode. Owns its own DB session."""
    with get_session_factory()() as db:
        execute_job(db, get_storage(), get_settings(), job_id)


def make_enqueue(settings: Settings, background_tasks: BackgroundTasks) -> Enqueue:
    if settings.job_backend == "celery":
        from app.workers.celery_app import celery_app  # imported lazily: inline mode needs no Redis

        def send(job_id: uuid.UUID) -> None:
            celery_app.send_task("omniiq.run_job", args=[str(job_id)])

        return send

    def inline(job_id: uuid.UUID) -> None:
        background_tasks.add_task(run_job_in_new_session, job_id)

    return inline
