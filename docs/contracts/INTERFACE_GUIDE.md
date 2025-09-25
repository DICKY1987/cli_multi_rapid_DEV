# CLI ↔ VS Code Extension Interface Guide

This guide defines the minimal, versioned contract between the Python CLI orchestrator and the VS Code extension. It covers request/response shapes and status/event streaming for workflow execution.

## Versioning
- Contract version: v1
- Backward-compatible additions allowed. Breaking changes require increment and changelog.

## HTTP Endpoints (local dev)
- POST `/api/workflows/start` → Start a workflow
  - Request: `WorkflowStartRequest`
  - Response: `WorkflowAccepted`
- GET `/api/workflows/{run_id}/status` → Poll current status
  - Response: `WorkflowStatus`
- GET `/api/workflows/{run_id}/events` → Server-sent events (SSE) stream of `WorkflowEvent`

## Data Models
- `WorkflowStartRequest`:
  - `workflow_id: string` (e.g., "CODE_QUALITY")
  - `files: string[]` (globs ok)
  - `parameters: object` (optional, free-form)
- `WorkflowAccepted`:
  - `run_id: string`
  - `queued_at: iso-datetime`
- `WorkflowStatus`:
  - `run_id: string`
  - `phase: "queued" | "running" | "completed" | "failed"`
  - `progress: number` (0..100)
  - `updated_at: iso-datetime`
  - `result?: object` (on completed)
  - `error?: { code: string; message: string }` (on failed)
- `WorkflowEvent` (SSE):
  - `type: "phase_started" | "phase_completed" | "artifact_emitted" | "error"`
  - `payload: object`
  - `ts: iso-datetime`

## Transport Notes
- Authentication: local development typically none; production token/TLS recommended.
- Serialization: JSON UTF-8.

## Error Handling
- 4xx for client input errors (invalid model/schema); 5xx for server faults.
- Error body: `{ code, message, details? }`.

## Mapping to Python Models
See `src/cli_multi_rapid/contracts/models.py` for canonical Pydantic definitions used by the CLI.

## Acceptance Criteria
- Extension sends `WorkflowStartRequest` and handles `WorkflowAccepted`.
- Extension can poll `/status` and render `WorkflowStatus` transitions.
- Extension can subscribe to `/events` and render `WorkflowEvent` messages.
- Contract tests validate JSON schema round-trip.
