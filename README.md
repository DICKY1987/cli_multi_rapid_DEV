cli-multi-rapid

Deterministic, schema-driven CLI orchestrator that routes between deterministic tools and AI agents.

Quick start
- Create and activate a virtualenv (Python 3.9+).
- Install dev deps: `pip install -e .[dev]`
- Run tests: `pytest -q`
- Lint: `ruff check .`; Format: `black .`; Sort imports: `isort .`; Type check: `mypy src`
- CLI help: `cli-orchestrator --help`
- Verify an artifact: `cli-orchestrator artifact.json --schema schema.json`

Project structure
- Source: `src/cli_multi_rapid` (orchestrator); libs: `src/integrations`, `src/websocket`, `src/observability`, `src/idempotency`.
- Workflows: `.ai/workflows/` (YAML), schemas: `.ai/schemas/` (JSON Schema).
- Tests: `tests/`; Docs: `docs/`; Config: `config/`; Scripts: `scripts/`.

Notes
- The recovered repo includes a large historical `main.py`. The published console script uses a minimal `cli_app.py` wrapper to ensure stable execution on Windows terminals.
- Coverage gate is configured at 85% targeting the simple verifier module initially; expand tests to cover additional modules as you iterate.
