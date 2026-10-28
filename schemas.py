from datetime import datetime
from uuid import UUID
from typing import Optional

from pydantic import BaseModel


class ReportRequest(BaseModel):
    period_start: datetime
    period_end: datetime


class ReportJobResponse(BaseModel):
    id: UUID
    status: str
    period_start: datetime
    period_end: datetime
    artifact_url: Optional[str] = None
    error_message: Optional[str] = None

    class Config:
        from_attributes = True