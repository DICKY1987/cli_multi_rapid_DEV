Verification Checkpoints Framework

Purpose
- Standardize gates (lint, tests, schema/security validators) as plugins invoked at checkpoints.

Plugin locations
- `verify.d/pytest.py` – runs pytest
- `verify.d/ruff_semgrep.py` – lint and static checks
- `verify.d/schema_validate.py` – schema validations
- `lib/verification_framework.py` – discovery and orchestration

CLI
- `ipt verify --checkpoint <id>` (concept) executes configured plugins and returns PASS/FAIL with reasons.

CI Integration
- Mirror the same plugin set in CI (`task ci`).

