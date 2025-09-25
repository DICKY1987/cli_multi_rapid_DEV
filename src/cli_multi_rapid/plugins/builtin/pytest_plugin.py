#!/usr/bin/env python3
"""
Pytest Plugin for CLI Orchestrator

Executes pytest and generates structured test reports.
"""

import json
import subprocess
from pathlib import Path
from typing import Any, Dict

try:
    from rich.console import Console

    console = Console()
except ImportError:
    # Fallback to basic print if rich is not available
    class Console:
        def print(self, text, style=None):
            clean_text = text
            for marker in [
                "[red]",
                "[/red]",
                "[green]",
                "[/green]",
                "[yellow]",
                "[/yellow]",
                "[blue]",
                "[/blue]",
            ]:
                clean_text = clean_text.replace(marker, "")
            print(clean_text)

    console = Console()

from ..base_plugin import BasePlugin, PluginResult


class PytestPlugin(BasePlugin):
    """Plugin for running pytest tests."""

    def __init__(self):
        super().__init__("pytest", "1.0.0")

    def get_capabilities(self) -> Dict[str, Any]:
        """Return plugin capabilities."""
        return {
            "description": "Executes pytest tests with coverage and structured reporting",
            "supported_formats": ["json", "junit"],
            "requires_tools": ["pytest"],
            "outputs": ["test_results.json", "coverage.json"],
            "gate_types": ["tests_pass", "coverage_threshold"],
        }

    def validate_config(self, config: Dict[str, Any]) -> bool:
        """Validate pytest plugin configuration."""
        # Optional fields with defaults
        test_paths = config.get("test_paths", ["tests/"])
        coverage_threshold = config.get("coverage_threshold", 80)

        if not isinstance(test_paths, list):
            console.print("[red]test_paths must be a list[/red]")
            return False

        if (
            not isinstance(coverage_threshold, (int, float))
            or not 0 <= coverage_threshold <= 100
        ):
            console.print(
                "[red]coverage_threshold must be a number between 0 and 100[/red]"
            )
            return False

        return True

    def get_required_tools(self) -> list[str]:
        """Return required tools."""
        return ["pytest"]

    def execute(
        self, config: Dict[str, Any], artifacts_dir: Path, context: Dict[str, Any]
    ) -> PluginResult:
        """Execute pytest tests."""

        # Configuration with defaults
        test_paths = config.get("test_paths", ["tests/"])
        coverage_threshold = config.get("coverage_threshold", 80)
        pytest_args = config.get("pytest_args", [])

        # Ensure artifacts directory exists
        artifacts_dir.mkdir(parents=True, exist_ok=True)

        # Prepare pytest command
        cmd = (
            [
                "pytest",
                "--json-report",
                "--json-report-file",
                str(artifacts_dir / "test_results.json"),
                "--cov=src",
                "--cov-report=json:" + str(artifacts_dir / "coverage.json"),
                "--cov-report=term-missing",
                "-v",
            ]
            + pytest_args
            + test_paths
        )

        try:
            # Execute pytest
            console.print(f"[blue]Running pytest: {' '.join(cmd)}[/blue]")
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                cwd=context.get("working_dir", Path.cwd()),
            )

            # Parse results
            test_results_file = artifacts_dir / "test_results.json"
            coverage_file = artifacts_dir / "coverage.json"

            # Load test results
            test_data = {}
            if test_results_file.exists():
                with open(test_results_file, encoding="utf-8") as f:
                    test_data = json.load(f)

            # Load coverage results
            coverage_data = {}
            if coverage_file.exists():
                with open(coverage_file, encoding="utf-8") as f:
                    coverage_data = json.load(f)

            # Extract metrics
            tests_passed = test_data.get("summary", {}).get("passed", 0)
            tests_failed = test_data.get("summary", {}).get("failed", 0)
            tests_total = tests_passed + tests_failed

            coverage_percent = coverage_data.get("totals", {}).get("percent_covered", 0)

            # Determine success
            tests_ok = tests_failed == 0 and tests_total > 0
            coverage_ok = coverage_percent >= coverage_threshold
            overall_passed = tests_ok and coverage_ok

            # Build message
            if not tests_ok:
                message = f"Tests failed: {tests_failed}/{tests_total} failed"
            elif not coverage_ok:
                message = f"Coverage below threshold: {coverage_percent:.1f}% < {coverage_threshold}%"
            else:
                message = f"All tests passed ({tests_total}) with {coverage_percent:.1f}% coverage"

            return PluginResult(
                plugin_name=self.name,
                passed=overall_passed,
                message=message,
                details={
                    "tests_total": tests_total,
                    "tests_passed": tests_passed,
                    "tests_failed": tests_failed,
                    "coverage_percent": coverage_percent,
                    "coverage_threshold": coverage_threshold,
                    "return_code": result.returncode,
                    "stdout": result.stdout,
                    "stderr": result.stderr,
                },
                artifacts_created=["test_results.json", "coverage.json"],
            )

        except Exception as e:
            return PluginResult(
                plugin_name=self.name,
                passed=False,
                message=f"Pytest execution failed: {e}",
                details={"error": str(e)},
            )
