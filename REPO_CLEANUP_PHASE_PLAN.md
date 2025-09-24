# Repository Cleanup Phase Plan

This plan outlines each actionable step to fully clean up and optimize your repository after a major consolidation. Use this as a checklist or project board reference.

---

## **Phase 1: Branch Cleanup**
- [ ] Delete all branches except `main` and `combined-updates`
  _Branches to delete:_
  - copilot/fix-4f67335c-a9b9-491a-ada4-6e521da8d443
  - chore/remove-gdw
  - chore/repo-cleanup-20250920
  - ci/phase-a-scaffold-20250920
  - docs/add-agents-md-20250920
  - docs/add-cli-updates-2025-09-20
  - feat/enhanced-prompt-execution
  - feat/phase-plan-complete
  - feat/phase-plan-complete-v2
  - feature/ai-adapters-implementation
  - feature/phase-b-contracts-scaffold-20250920
  - ops/issues-milestones-automation-20250920
  - rel/v0.1.0-hardening

---

## **Phase 2: Issues & Pull Requests Audit**
- [ ] Review and close any resolved or obsolete issues:
    - [ ] Raise coverage to >=85% on extended CI ([#13](https://github.com/DICKY1987/cli_multi_rapid_DEV/issues/13))
    - [ ] Decide and implement/remove `gdw` CLI subcommand ([#12](https://github.com/DICKY1987/cli_multi_rapid_DEV/issues/12))
    - [ ] Websocket integration test dependency handling ([#11](https://github.com/DICKY1987/cli_multi_rapid_DEV/issues/11))
    - [ ] SyntaxError in lib/cost_tracker.py ([#10](https://github.com/DICKY1987/cli_multi_rapid_DEV/issues/10))
    - [ ] Benchmark import fails ([#9](https://github.com/DICKY1987/cli_multi_rapid_DEV/issues/9))
- [ ] Close any stale or unmerged pull requests.

---

## **Phase 3: Tags & Releases**
- [ ] Review tags and releases for outdated or obsolete entries.
- [ ] Remove or update as required.

---

## **Phase 4: Documentation Update**
- [ ] Update README.md and other documentation to reflect the current branch structure.
- [ ] Remove references to deleted branches and obsolete features.
- [ ] Review key docs for outdated information:
    - [README.md](https://github.com/DICKY1987/cli_multi_rapid_DEV/blob/main/README.md)
    - [docs/README.md](https://github.com/DICKY1987/cli_multi_rapid_DEV/blob/main/docs/README.md)
    - [docs/COMPLETE_IMPLEMENTATION_PLAN.md](https://github.com/DICKY1987/cli_multi_rapid_DEV/blob/main/docs/COMPLETE_IMPLEMENTATION_PLAN.md)
    - [docs/roadmap.md](https://github.com/DICKY1987/cli_multi_rapid_DEV/blob/main/docs/roadmap.md)
    - [docs/STRUCTURE.md](https://github.com/DICKY1987/cli_multi_rapid_DEV/blob/main/docs/STRUCTURE.md)

---

## **Phase 5: CI/CD & Workflow Cleanup**
- [ ] Audit GitHub Actions workflows and configs ([test_workflow.yaml](https://github.com/DICKY1987/cli_multi_rapid_DEV/blob/main/test_workflow.yaml), [.github](https://github.com/DICKY1987/cli_multi_rapid_DEV/tree/main/.github))
- [ ] Ensure workflows reference only active branches.
- [ ] Remove jobs for deleted branches.

---

## **Phase 6: Security & Access Audit**
- [ ] Review repository secrets/tokens and remove unused entries.
- [ ] Audit collaborator and team access, removing unnecessary access.

---

## **Phase 7: Dependency Cleanup**
- [ ] Prune unused dependencies (pip uninstall, npm prune, etc.).
- [ ] Review and update `requirements.txt` and `pyproject.toml`.

---

## **Phase 8: Code Quality & Artifacts**
- [ ] Run linters and formatters (black, flake8, pre-commit, etc.).
- [ ] Remove commented-out code and unused files.
- [ ] Clean up leftover test data, logs, or artifacts.

---

## **Phase 9: Backup & Tagging**
- [ ] Create a backup tag or release for the current state before final deletion (optional but recommended).

---

**Tracking:**
- Convert this plan into a GitHub Project or Issue for progress tracking.
- Check off each phase as completed.

---

_Last updated: 2025-09-20_
