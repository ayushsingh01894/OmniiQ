import uuid

from app.workers.celery_app import celery_app
from app.workers.dispatch import run_job_in_new_session


@celery_app.task(name="omniiq.run_job")
def run_job(job_id: str) -> None:
    run_job_in_new_session(uuid.UUID(job_id))
