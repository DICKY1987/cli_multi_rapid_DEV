from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class Phase(str, Enum):
    queued = "queued"
    running = "running"
    completed = "completed"
    failed = "failed"


class WorkflowStartRequest(BaseModel):
    workflow_id: str = Field(..., min_length=1)
    files: List[str] = Field(default_factory=list)
    parameters: Dict[str, Any] = Field(default_factory=dict)


class WorkflowAccepted(BaseModel):
    run_id: str
    queued_at: datetime


class WorkflowError(BaseModel):
    code: str
    message: str
    details: Optional[Dict[str, Any]] = None


class WorkflowStatus(BaseModel):
    run_id: str
    phase: Phase
    progress: float = Field(ge=0, le=100, default=0)
    updated_at: datetime
    result: Optional[Dict[str, Any]] = None
    error: Optional[WorkflowError] = None


class EventType(str, Enum):
    phase_started = "phase_started"
    phase_completed = "phase_completed"
    artifact_emitted = "artifact_emitted"
    error = "error"


class WorkflowEvent(BaseModel):
    type: EventType
    payload: Dict[str, Any]
    ts: datetime


__all__ = [
    "Phase",
    "WorkflowStartRequest",
    "WorkflowAccepted",
    "WorkflowError",
    "WorkflowStatus",
    "EventType",
    "WorkflowEvent",
]
