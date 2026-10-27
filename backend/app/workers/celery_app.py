import logging
from typing import Any

from celery import Celery
from celery.signals import worker_ready

from app.core.config import Settings, get_settings
from app.core.logging import configure_logging

logger = logging.getLogger(__name__)


def create_celery(settings: Settings) -> Celery:
    app = Celery("omniiq", broker=settings.redis_url, include=["app.workers.tasks"])
    app.conf.update(
        task_ignore_result=True,  # results live in the data_jobs table, not in Redis
        task_acks_late=True,  # a job is only acknowledged after it finished
        task_reject_on_worker_lost=True,
        worker_prefetch_multiplier=1,  # long jobs: don't hoard tasks
        task_soft_time_limit=max(settings.job_time_limit_seconds - 30, 5),
        task_time_limit=settings.job_time_limit_seconds,
        broker_connection_retry_on_startup=True,
        worker_hijack_root_logger=False,
    )
    return app


celery_app = create_celery(get_settings())


@worker_ready.connect
def _on_worker_ready(**_: Any) -> None:
    """After a (re)start, jobs that were 'running' for far too long belong to a dead worker."""
    from app.db.session import get_session_factory
    from app.services.datasets.jobs import fail_stale_jobs

    settings = get_settings()
    configure_logging(settings.log_level)
    with get_session_factory()() as db:
        count = fail_stale_jobs(db, max_age_seconds=settings.job_time_limit_seconds * 2)
    if count:
        logger.warning("marked %d stale job(s) as failed", count)
