# Stakeholder Reports

## Technical Team
**Prioritized Tasks**
- Wire multi-language CI gates: Python (pytest, ruff, mypy, coverage), TS (eslint/tsc/unit), VSCode extension build, MQL4 lint/build.
- Consolidate environment: devcontainer + docker-compose; one `.env` contract and secrets policy.
- Orchestrate with Taskfile: `task ci`, `task test`, `task lint`, `task e2e`, `task release`.
- Observability: shipping logs/metrics; Grafana dashboards validated.
- Cross-repo packaging: `pyproject.toml` standards; version pinning and reproducible builds.

**Quality Gates**
- Lint/type/test/security/build must pass on PR.
- 80%+ coverage on core paths in A; 90%+ by B.
- No critical/high vulns; secret scans clean.

**Acceptance Criteria Examples**
- `task ci` exits 0 on clean repo.
- `docker compose up -d` brings stack healthy; `/healthz` returns 200.
- VS Code extension installs locally and completes a sample workflow.

## Business Team
**Roadmap & Impact**
- Phase A unlocks reliable iteration cadence (velocity ↑, rework ↓).
- Phase B delivers integrated CLI/GUI/extension workflows with cost controls.
- KPIs: lead time for change, change failure rate, MTTR, AI token cost per change, number of automated checks per PR.

**Risks & Mitigations**
- Toolchain drift → lockfiles, Taskfile, nightly CI dry runs.
- Multi-language fragility → contract tests + smoke E2E.
- Secret exposure → pre-commit hooks + baseline scans + rotation playbook.

## Operations Team
**Deployment & Ops**
- Compose for local; K8s for staging/prod with GitHub Actions.
- Monitoring: alerts for error rate, latency, and token-cost anomalies.
- Runbooks: deploy/rollback, incident response, backup/restore.

**SLA Targets**
- P95 latency < 300ms for core CLI API.
- <1% error rate over rolling 30 days.
- 99.5% availability once in prod.

