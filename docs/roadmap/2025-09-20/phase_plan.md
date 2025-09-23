# Phase Plan – Implement Recommended Modifications (2025-09-20)

This plan operationalizes the roadmap/backlog to deliver a production-ready CLI Multi‑Rapid framework with CLI↔GUI↔VS Code parity, strong CI/CD, and observability.

## Phase A – Foundation Stabilization (Week 1–2)
- CI matrix: Add `.github/workflows/ci-matrix.yml` with jobs: Python (ruff, mypy, pytest+coverage), TypeScript (eslint, tsc, unit), MQL4 (lint/build) and security (CodeQL, secret scan).
- Dependency pinning: Introduce lockfiles (`requirements.lock` via pip‑tools/uv, `pnpm-lock.yaml`), and `.env.template` with minimal required variables.
- Taskfile orchestration: Expand `Taskfile.yml` with `ci`, `local`, `lint`, `type`, `test`, `e2e`, `release`, `dotenv`.
- Secrets policy: Add `.pre-commit-config.yaml` with `detect-secrets` and `pre-commit` hooks; baseline via `.secrets.baseline`.
- Compose smoke: Add `docker-compose.yml` with core services and `/healthz`; create `scripts/healthcheck.py` and a GH Action step to validate 200 OK.

Acceptance Criteria
- `task ci` runs all local gates successfully on clean checkout.
- CI status: all blocking jobs green; artifacts and coverage uploaded.
- `docker compose up -d` and `/healthz` returns 200 in <2s in CI.

## Phase B – Core Feature Development (Week 3–6)
- Shared contracts: Define CLI↔VS Code API (e.g., `docs/contracts/INTERFACE_GUIDE.md`) and ensure extension parity.
- GUI integration: Wire `CLI_PY_GUI` to orchestration; add server stubs and tests.
- LangGraph bridge: Implement `langgraph_cli.py` and `langgraph_git_integration.py` for git‑aware flows.
- Contract & integration tests: Add `tests/contracts/` and `tests/integration/` suites; Playwright for extension path.

Acceptance Criteria
- CLI↔Extension contract tests pass locally and in CI.
- Coverage on critical paths ≥ 90%.

## Phase C – Production Readiness (Week 7–9)
- K8s manifests: `deploy/k8s/**` with rollout/rollback; GH Actions deploy to staging.
- Monitoring: Grafana dashboards and Prometheus scrape configs; `/metrics` exported.
- Performance & load tests: `tests/perf/**` and CI job; hit SLOs.

Acceptance Criteria
- Canary deploy succeeds; rollback verified.
- Dashboards show live metrics; alerts configured.
- Perf tests meet P95 < 300ms; error rate < 1%.

## Phase D – Launch & Stabilization (Week 10–12)
- Documentation & training: Developer onboarding, admin runbooks, incident response.
- Release pipeline: Tag‑based build/sign/publish; SBOM & signatures attached.
- Maintenance: Dependency update cadence; nightly CI dry‑runs; coverage ratcheting.

Acceptance Criteria
- Release pipeline produces signed artifacts.
- Runbooks complete; contributors can follow lanes reliably.

## Work Breakdown to Issues (initial)
- A‑1: Create CI matrix and gates (owner: infra). Path: `.github/workflows/ci-matrix.yml`.
- A‑2: Add lockfiles and `.env.template` (owner: platform).
- A‑3: Expand Taskfile targets (owner: platform).
- A‑4: Pre‑commit hooks + secret scan (owner: security).
- A‑5: Compose + healthcheck + CI E2E smoke (owner: infra).
- B‑1: Contracts guide + extension parity (owner: UI/ext).
- B‑2: GUI integration stubs + tests (owner: UI/backend).
- B‑3: LangGraph CLI + git integration (owner: platform).
- B‑4: Contracts/integration tests + coverage (owner: QA/SDET).
- C‑1..D‑3: K8s, monitoring, perf, release, docs (owners: infra/security/QA).

## Commands & Conventions
- Run locally: `task ci` or `task local`.
- Compose: `docker compose up -d && python scripts/healthcheck.py http://localhost:8000/healthz`.
- Tests: `pytest -q --cov=src --cov-report=xml` and `pnpm test`.
- Lint/type: `ruff check . && mypy src` and `pnpm lint && pnpm typecheck`.
