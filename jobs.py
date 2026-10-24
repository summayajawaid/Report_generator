import logging
from datetime import datetime
from uuid import UUID

from sqlalchemy.orm import Session

from .database import SessionLocal
from .models import ReportJob, JobStatus
from .queries import get_workshop_summary, get_totals
from .pdf_report import render_workshop_report_pdf

logger = logging.getLogger(__name__)

# Where generated PDFs are served from. In this simple in-process pattern
# we serve them straight off disk via a FastAPI StaticFiles / download route.
# Swap this for an S3 presigned URL if/when you move off local storage.
ARTIFACT_URL_PREFIX = "/reports/download"


def run_report_job(job_id: UUID) -> None:
    """
    The actual background job body, run via FastAPI's BackgroundTasks.

    IMPORTANT: this function opens its OWN database session rather than
    reusing the request's session. BackgroundTasks run *after* the request
    has already returned, so the request-scoped `db` dependency will have
    been closed by then -- this is the #1 bug people hit with this pattern.
    """
    db: Session = SessionLocal()
    try:
        job = db.query(ReportJob).filter(ReportJob.id == job_id).first()
        if job is None:
            logger.error("run_report_job: job %s not found", job_id)
            return

        job.status = JobStatus.RUNNING
        job.updated_at = datetime.utcnow()
        db.commit()

        # 1. Query + aggregate
        totals = get_totals(db, job.period_start, job.period_end)
        summary_rows = get_workshop_summary(db, job.period_start, job.period_end)

        # 2. Render PDF
        filepath = render_workshop_report_pdf(
            job_id=str(job.id),
            period_start=job.period_start,
            period_end=job.period_end,
            totals=totals,
            summary_rows=summary_rows,
        )

        # 3. Record the artifact pointer only -- never the file bytes
        job.artifact_path = filepath
        job.artifact_url = f"{ARTIFACT_URL_PREFIX}/{job.id}"
        job.status = JobStatus.DONE
        job.updated_at = datetime.utcnow()
        db.commit()

    except Exception as exc:  # noqa: BLE001 -- we want to capture ANY failure
        logger.exception("run_report_job failed for %s", job_id)
        db.rollback()
        job = db.query(ReportJob).filter(ReportJob.id == job_id).first()
        if job:
            job.status = JobStatus.FAILED
            job.error_message = str(exc)
            job.updated_at = datetime.utcnow()
            db.commit()
    finally:
        db.close()