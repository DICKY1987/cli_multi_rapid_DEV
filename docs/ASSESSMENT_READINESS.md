Assessment Readiness Plan

Goals

- Ensure repo is ready for code review and automated assessment.
- Make it easy to run quality, security, and schema gates locally and in CI.

Check Commands

- Pre-commit (format/lint/security):
  - pip install pre-commit
  - pre-commit install
  - pre-commit run --all-files
- Contracts & Schemas:
  - pip install jsonschema
  - python scripts/contracts_validate.py
  - python scripts/schema_diff.py (on branches with base ref)
- Registry Codegen:
  - pip install pyyaml
  - python scripts/registry_codegen.py --check
- Tests & Coverage:
  - poetry install
  - pytest -q --cov=services
- Security (optional locally):
  - pip install bandit safety semgrep
  - bandit -q -r ./
  - safety check --full-report

CI Gates (added)

- contracts-validate.yml — validates schemas and events
- schema-diff.yml — enforces SemVer on schema changes
- registry-codegen.yml — ensures generated files are up to date

Branching & PRs

- Use feature branches per phase (e.g., chore/phase0-1-scaffolding)
- Open PRs early; CI will run schema/codegen gates

Milestones & Issues

- Use scripts/gh_seed_issues.py with GitHub CLI:
  - gh auth login
  - python scripts/gh_seed_issues.py --repo <owner/repo> \
    --milestones planning/issues_phase_0_1.yaml planning/issues_phase_2_6.yaml planning/issues_phase_7_12.yaml \
    --issues planning/issues_phase_0_1.yaml planning/issues_phase_2_6.yaml planning/issues_phase_7_12.yaml
