# Coordination Guide

This guide explains how to use the coordination features of the CLI Orchestrator to run multiple workflows safely with conflict detection, budget awareness, and basic monitoring/reporting.

## Commands

Examples assume you have installed the project:

```
pip install -e .[dev]
```

Or use `PYTHONPATH=src python -m cli_multi_rapid.main` locally.

### Plan

Create a coordination plan from one or more workflow YAMLs and detect file-scope conflicts:

```
cli-orchestrator coordination plan .ai/workflows/CODE_QUALITY.yaml --output artifacts/plan.json
```

### Run (dry)

Execute workflows with coordination (dry-run to preview):

```
cli-orchestrator coordination run .ai/workflows/CODE_QUALITY.yaml --mode parallel --max-parallel 3 --budget 40 --dry-run
```

This writes a session summary to `state/coordination/<id>.json`.

### Status / Cancel

```
cli-orchestrator coordination status <coord_id>
cli-orchestrator coordination cancel <coord_id>
```

Cancel is cooperative and writes a `<coord_id>.cancel` flag that the runner checks.

### Dashboard

```
cli-orchestrator coordination dashboard --iterations 1 --id <coord_id>
```

Shows a simple live table based on the persisted state.

### Reports & History

```
cli-orchestrator coordination report <coord_id> --format json|csv|html --output artifacts/reports/<file>
cli-orchestrator coordination history --days 7 [--workflow <filter>]
```

## Configuration

Optional defaults can be set in `.ai/config/coordination.yaml`:

```yaml
coordination:
  default_mode: parallel
  max_parallel_workflows: 5
  default_budget: 30.0
  timeout_minutes: 60
  resource_limits:
    max_memory_mb: 2048
    max_cpu_percent: 80
    max_file_handles: 1000
  retry_policy:
    max_attempts: 3
    backoff_seconds: [1, 5, 15]
  security:
    default_level: medium
    isolation_enabled: true
    network_access: false
```

If CLI flags are left at their defaults, the loader applies the config values.

## Notes

- File-scope claims and conflicts are derived from workflow metadata and phases.
- State files live under `state/coordination/` (git-ignored).
- For richer telemetry or a multi-process dashboard, integrate the event bus service.

