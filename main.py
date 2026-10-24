from uuid import UUID

from fastapi import FastAPI, BackgroundTasks, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from .database import get_db, engine
from .models import Base, ReportJob, JobStatus
from .schemas import ReportRequest, ReportJobResponse
from .jobs import run_report_job

app = FastAPI(title="Workshop PDF Report Generator")

# In a real project you'd use Alembic migrations instead of create_all.
Base.metadata.create_all(bind=engine)


@app.post("/reports", response_model=ReportJobResponse, status_code=202)
def create_report(
    payload: ReportRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """
    Kick off report generation as a background job.

    Returns immediately (202 Accepted) with a job_id in PENDING state --
    it does NOT wait for the PDF to be built. Poll GET /reports/{id} for
    status, and follow artifact_url once status == "done".
    """
    job = ReportJob(
        status=JobStatus.PENDING,
        period_start=payload.period_start,
        period_end=payload.period_end,
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    # Runs after the response is sent. See jobs.py for why it opens its
    # own DB session instead of reusing this request's `db`.
    background_tasks.add_task(run_report_job, job.id)

    return job


@app.get("/reports/{job_id}", response_model=ReportJobResponse)
def get_report_status(job_id: UUID, db: Session = Depends(get_db)):
    job = db.query(ReportJob).filter(ReportJob.id == job_id).first()
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@app.get("/reports/download/{job_id}")
def download_report(job_id: UUID, db: Session = Depends(get_db)):
    """
    Serves the actual PDF bytes. This is the ONLY place the file content
    itself is streamed -- everywhere else in the API we only ever pass
    around the small artifact_url pointer, per the assignment's "don't
    pass 20 MB around" rule.
    """
    job = db.query(ReportJob).filter(ReportJob.id == job_id).first()
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.status != JobStatus.DONE or not job.artifact_path:
        raise HTTPException(status_code=409, detail=f"Report not ready (status={job.status})")

    return FileResponse(
        path=job.artifact_path,
        media_type="application/pdf",
        filename=f"workshop_report_{job_id}.pdf",
    )