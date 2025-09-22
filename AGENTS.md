# Repository Guidelines

## Project Structure & Module Organization
- Source: `src/cli_multi_rapid` (CLI orchestrator), supporting libs: `src/integrations`, `src/websocket`, `src/observability`, `src/idempotency`.
- Workflows: `.ai/workflows/` (YAML), `.ai/schemas/` (JSON Schemas).
- Tests: `tests/` (unit/integration/benchmarks); Docs: `docs/` (guides, contracts);
  Extension: `vscode-extension/`; Config: `config/`; Scripts: `scripts/`.

## Build, Test, and Development Commands
- Setup (dev): `pip install -e .[dev]` (Python), `npm ci` in `vscode-extension/`.
- Quick checks: `task ci` (ruff, mypy, pytest + coverage gate).
- Run tests: `pytest -q --cov=src --cov-fail-under=85`.
- Compose smoke: `docker compose -f config/docker-compose.yml up -d` then
  `python scripts/healthcheck.py http://localhost:5055/health`.
- Orchestrator (dry-run): `cli-orchestrator run .ai/workflows/CODE_QUALITY.yaml --dry-run`.
- Extension CI: `(cd vscode-extension && npm run ci)`.

## Coding Style & Naming Conventions
- Python 3.9+, 4-space indents, prefer type hints. Names: snake_case for modules/functions; PascalCase for classes.
- Lint/format/type: `ruff`, `black`, `isort`, `mypy`. Install pre-commit hooks: `pre-commit install`.
- Keep changes minimal, deterministic, and schema-driven.

## Testing Guidelines
- Framework: `pytest`; coverage gate: ≥ 85% (enforced in CI).
- Naming: files `tests/test_*.py`, classes `Test*`, functions `test_*`.
- Contract tests live under `tests/contracts/`; see `docs/contracts/INTERFACE_GUIDE.md` for models.

## Commit & Pull Request Guidelines
- Use Conventional Commits (e.g., `feat:`, `fix:`, `chore:`) with concise scope.
- Before PR: run `task ci` and the compose smoke test; ensure no secrets/keys in diffs.
- PRs include: clear description, linked issues/milestones, and any artifacts (coverage, screenshots/logs where relevant).

## Security & Configuration Tips
- Do not commit secrets. Secret scans run via pre-commit (`detect-secrets`) and CI; baseline: `.secrets.baseline`.
- Copy `.env.template` to `.env` for local runs; never push `.env`.
- Prefer deterministic tools first; avoid networked calls in tests.

## Agent-Specific Instructions
- Follow this AGENTS.md across the repo. Validate workflows with dry-runs, respect schemas, and keep outputs reproducible. When in doubt, propose changes in small, reviewable PRs.

