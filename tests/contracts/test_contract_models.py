from __future__ import annotations
from datetime import datetime

from cli_multi_rapid.contracts.models import (
    Phase,
    WorkflowAccepted,
    WorkflowError,
    WorkflowEvent,
    WorkflowStartRequest,
    WorkflowStatus,
    EventType,
)


def test_start_request_roundtrip():
    req = WorkflowStartRequest(workflow_id="CODE_QUALITY", files=["src/**/*.py"], parameters={"dry_run": True})
    data = req.model_dump()
    again = WorkflowStartRequest(**data)
    assert again.workflow_id == "CODE_QUALITY"
    assert again.parameters["dry_run"] is True


def test_status_progress_and_error():
    now = datetime.utcnow()
    status = WorkflowStatus(run_id="r1", phase=Phase.running, progress=50.0, updated_at=now)
    assert status.progress == 50.0
    # attach an error
    err = WorkflowError(code="E1", message="boom")
    status.phase = Phase.failed
    status.error = err
    assert status.error.code == "E1"


def test_accepted_and_event():
    now = datetime.utcnow()
    acc = WorkflowAccepted(run_id="r1", queued_at=now)
    assert acc.run_id == "r1"

    evt = WorkflowEvent(type=EventType.phase_started, payload={"name": "lint"}, ts=now)
    assert evt.payload["name"] == "lint"

