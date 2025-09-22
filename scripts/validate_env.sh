#!/usr/bin/env bash
set -euo pipefail

# First, run the guard check
"$(dirname "$0")/guard_cwd.sh"

fail=0

# Check if .claude.json is properly ignored
if git check-ignore -q .claude.json; then
    :  # File is ignored, good
else
    echo ".claude.json is not ignored (security risk)"
    fail=1
fi

# Check for pre-commit configuration and run hooks
if [[ -f ".pre-commit-config.yaml" ]]; then
    if command -v pre-commit >/dev/null 2>&1; then
        echo "Running pre-commit hooks (may modify files)..."
        pre-commit run --all-files || fail=1
    else
        echo "pre-commit not installed; skipping hook validation."
    fi
else
    echo ".pre-commit-config.yaml not found"
    fail=1
fi

# Report results
if [[ $fail -ne 0 ]]; then
    echo "== VALIDATE: FAIL =="
    exit 1
else
    echo "== VALIDATE: OK =="
fi
