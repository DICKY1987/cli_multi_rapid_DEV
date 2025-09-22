#!/usr/bin/env bash
set -euo pipefail

# Get the Git repository root
TOPLEVEL="$(git rev-parse --show-toplevel 2>/dev/null || true)"
if [[ -z "${TOPLEVEL}" ]]; then
    echo "Not inside a Git repository." >&2
    exit 1
fi

# Check if repo root equals HOME (the core issue)
if [[ "$TOPLEVEL" == "$HOME" ]]; then
    echo "Refusing: repo root equals HOME ($HOME). cd to the real project root." >&2
    exit 1
fi

echo "Repo root OK: $TOPLEVEL"
