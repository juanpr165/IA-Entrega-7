from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class JobStatus(StrEnum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    WAITING_APPROVAL = "WAITING_APPROVAL"
    DONE = "DONE"
    FAILED = "FAILED"


class TaskCreate(BaseModel):
    task: str = Field(min_length=1, max_length=12_000)


class TaskAccepted(BaseModel):
    job_id: str
    status: JobStatus


class ApprovalRequest(BaseModel):
    approved: bool
    reviewer_note: str | None = Field(default=None, max_length=2_000)


class JobRecord(BaseModel):
    job_id: str
    task: str
    status: JobStatus
    critical: bool
    created_at: datetime
    updated_at: datetime
    result: str | None = None
    error: str | None = None
    reviewer_note: str | None = None
    routing_history: list[dict[str, Any]] = Field(default_factory=list)
