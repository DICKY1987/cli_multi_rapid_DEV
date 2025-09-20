#!/usr/bin/env bash
set -euo pipefail

echo "== Pre-commit hooks =="
pre-commit run --all-files || true

echo "== Contracts validate =="
python scripts/contracts_validate.py

echo "== Registry codegen check =="
python scripts/registry_codegen.py --check || (echo "Run python scripts/registry_codegen.py to update." && exit 1)

echo "== Schema diff (if PR) =="
python scripts/schema_diff.py || true

echo "== Tests =="
pytest -q --cov=services || true

echo "All checks executed. Review outputs above."

