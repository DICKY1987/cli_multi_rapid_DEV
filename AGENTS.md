# AGENTS.md

- Source: `src/cli_multi_rapid` (CLI orchestrator), supporting libs: `src/integrations`, `src/websocket`, `src/observability`, `src/idempotency`.
- Workflows: `.ai/workflows/` (YAML), `.ai/schemas/` (JSON Schemas).
- Tests: `tests/` (unit/integration/benchmarks); Docs: `docs/` (guides, contracts);
  Extension: `vscode-extension/`; Config: `config/`; Scripts: `scripts/`.

Build & Test:
- Setup: `pip install -e .[dev]`
- Quick checks: `task ci`
- Tests: `pytest -q --cov=src --cov-fail-under=85`

Style:
- Python 3.9+, type hints, ruff/black/isort/mypy. Install hooks: `pre-commit install`.

Testing:
- `pytest`; coverage gate ≥ 85%.

Security:
- No secrets; use `.secrets.baseline`; use `.env.template` for local.

Agent:
- Validate workflows with dry-runs, respect schemas, reproducible outputs.
