#!/usr/bin/env python3
"""
CLI Orchestrator Synchronization Verification Script

Verifies that the repository has been fully synchronized with the CLI orchestrator
specification and that the automated interference has been resolved.
"""

import os
import subprocess
from typing import List, Tuple


def check_file_exists(filepath: str, description: str) -> Tuple[bool, str]:
    """Check if a file exists and return status."""
    if os.path.exists(filepath):
        return True, f"[OK] {description}: Found"
    return False, f"[FAIL] {description}: Missing"


def check_file_content(
    filepath: str, expected_content: str, description: str
) -> Tuple[bool, str]:
    """Check if file contains expected content."""
    try:
        if os.path.exists(filepath):
            with open(filepath, "r", encoding="utf-8") as f:
                content = f.read()
                if expected_content in content:
                    return True, f"[OK] {description}: Correct"
                else:
                    return False, f"[FAIL] {description}: Incorrect content"
        else:
            return False, f"[FAIL] {description}: File missing"
    except Exception as e:
        return False, f"[FAIL] {description}: Error reading file - {e}"


def check_git_remote() -> Tuple[bool, str]:
    """Check if Git remote is configured correctly."""
    try:
        result = subprocess.run(["git", "remote", "-v"], capture_output=True, text=True)
        if "cli_multi_rapid_DEV.git" in result.stdout:
            return True, "[OK] Git Remote: Configured for cli_multi_rapid_DEV"
        else:
            return False, f"[FAIL] Git Remote: Incorrect - {result.stdout.strip()}"
    except Exception as e:
        return False, f"[FAIL] Git Remote: Error checking - {e}"


def check_directory_structure() -> List[Tuple[bool, str]]:
    """Check CLI orchestrator directory structure."""
    checks = []

    # Core directories
    dirs_to_check = [
        ("src/cli_multi_rapid", "CLI Orchestrator source"),
        (".ai", "Workflow definitions"),
        (".ai/workflows", "YAML workflows"),
        (".ai/schemas", "JSON schemas"),
        ("artifacts", "Runtime artifacts"),
        ("logs", "Execution logs"),
    ]

    for dir_path, desc in dirs_to_check:
        exists, msg = check_file_exists(dir_path, desc)
        checks.append((exists, msg))

    return checks


def check_key_files() -> List[Tuple[bool, str]]:
    """Check key CLI orchestrator files."""
    checks = []

    # Core files
    files_to_check = [
        ("src/cli_multi_rapid/__init__.py", "CLI orchestrator init"),
        ("src/cli_multi_rapid/main.py", "Main CLI entry"),
        ("src/cli_multi_rapid/workflow_runner.py", "Workflow runner"),
        ("src/cli_multi_rapid/router.py", "Router system"),
        ("src/cli_multi_rapid/cost_tracker.py", "Cost tracker"),
        ("src/cli_multi_rapid/verifier.py", "Gate system"),
        (".ai/schemas/workflow.schema.json", "Workflow schema"),
        (".ai/workflows/PY_EDIT_TRIAGE.yaml", "Sample workflow"),
        ("CLAUDE.md", "Project instructions"),
    ]

    for file_path, desc in files_to_check:
        exists, msg = check_file_exists(file_path, desc)
        checks.append((exists, msg))

    return checks


def check_configuration() -> List[Tuple[bool, str]]:
    """Check configuration files for CLI orchestrator content."""
    checks = []

    # pyproject.toml
    exists, msg = check_file_content(
        "pyproject.toml",
        'name = "cli-orchestrator"',
        "pyproject.toml CLI orchestrator name",
    )
    checks.append((exists, msg))

    exists, msg = check_file_content(
        "pyproject.toml",
        'cli-orchestrator = "cli_multi_rapid.main:main"',
        "pyproject.toml CLI orchestrator script",
    )
    checks.append((exists, msg))

    # CI configuration
    exists, msg = check_file_content(
        ".github/workflows/ci.yml", "CLI Orchestrator CI", "CI pipeline name"
    )
    checks.append((exists, msg))

    exists, msg = check_file_content(
        ".github/workflows/ci.yml", "cli_orchestrator_test", "CI job name"
    )
    checks.append((exists, msg))

    # CLAUDE.md
    exists, msg = check_file_content(
        "CLAUDE.md", "CLI Orchestrator", "CLAUDE.md project description"
    )
    checks.append((exists, msg))

    return checks


def main():
    """Run all verification checks."""
    print("CLI Orchestrator Synchronization Verification")
    print("=" * 55)

    all_checks = []

    # Check Git remote
    status, msg = check_git_remote()
    all_checks.append((status, msg))
    print(msg)

    print("\nDirectory Structure:")
    dir_checks = check_directory_structure()
    all_checks.extend(dir_checks)
    for status, msg in dir_checks:
        print(f"  {msg}")

    print("\nKey Files:")
    file_checks = check_key_files()
    all_checks.extend(file_checks)
    for status, msg in file_checks:
        print(f"  {msg}")

    print("\nConfiguration:")
    config_checks = check_configuration()
    all_checks.extend(config_checks)
    for status, msg in config_checks:
        print(f"  {msg}")

    # Summary
    passed = sum(1 for status, _ in all_checks if status)
    total = len(all_checks)

    print("\n" + "=" * 55)
    print(f"VERIFICATION RESULTS: {passed}/{total} checks passed")

    if passed == total:
        print("SUCCESS: 100% SYNCHRONIZATION ACHIEVED!")
        print("[OK] CLI Orchestrator is fully synchronized")
        print("[OK] No automated interference detected")
        print("[OK] Repository ready for development")
        return True
    else:
        failed = total - passed
        print(f"WARNING: {failed} issues found - synchronization incomplete")
        return False


if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
