#!/usr/bin/env python3
"""
Ruff + Semgrep Plugin for CLI Orchestrator

Runs code quality and security analysis using ruff and semgrep.
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


class RuffSemgrepPlugin(BasePlugin):
    """Plugin for running ruff and semgrep analysis."""

    def __init__(self):
        super().__init__("ruff_semgrep", "1.0.0")

    def get_capabilities(self) -> Dict[str, Any]:
        """Return plugin capabilities."""
        return {
            "description": "Code quality and security analysis with ruff and semgrep",
            "supported_formats": ["json"],
            "requires_tools": ["ruff", "semgrep"],
            "outputs": [
                "ruff_results.json",
                "semgrep_results.json",
                "lint_summary.json",
            ],
            "gate_types": ["code_quality", "security_scan"],
        }

    def validate_config(self, config: Dict[str, Any]) -> bool:
        """Validate plugin configuration."""
        # Optional fields with defaults
        paths = config.get("paths", ["src/", "tests/"])
        ruff_rules = config.get("ruff_rules", [])
        semgrep_rules = config.get("semgrep_rules", ["auto"])
        max_violations = config.get("max_violations", 0)

        if not isinstance(paths, list):
            console.print("[red]paths must be a list[/red]")
            return False

        if not isinstance(ruff_rules, list):
            console.print("[red]ruff_rules must be a list[/red]")
            return False

        if not isinstance(max_violations, int) or max_violations < 0:
            console.print("[red]max_violations must be a non-negative integer[/red]")
            return False

        return True

    def get_required_tools(self) -> list[str]:
        """Return required tools."""
        return ["ruff", "semgrep"]

    def execute(
        self, config: Dict[str, Any], artifacts_dir: Path, context: Dict[str, Any]
    ) -> PluginResult:
        """Execute ruff and semgrep analysis."""

        # Configuration with defaults
        paths = config.get("paths", ["src/", "tests/"])
        ruff_rules = config.get("ruff_rules", [])
        semgrep_rules = config.get("semgrep_rules", ["auto"])
        max_violations = config.get("max_violations", 0)

        # Ensure artifacts directory exists
        artifacts_dir.mkdir(parents=True, exist_ok=True)

        working_dir = context.get("working_dir", Path.cwd())

        results = {
            "ruff": {"success": False, "violations": 0, "details": {}},
            "semgrep": {"success": False, "violations": 0, "details": {}},
        }

        # Run ruff
        try:
            ruff_cmd = [
                "ruff",
                "check",
                "--format=json",
                "--output-file",
                str(artifacts_dir / "ruff_results.json"),
            ] + paths

            if ruff_rules:
                ruff_cmd.extend(["--select", ",".join(ruff_rules)])

            console.print(f"[blue]Running ruff: {' '.join(ruff_cmd)}[/blue]")
            ruff_result = subprocess.run(
                ruff_cmd, capture_output=True, text=True, cwd=working_dir
            )

            # Parse ruff results
            ruff_file = artifacts_dir / "ruff_results.json"
            if ruff_file.exists():
                with open(ruff_file, encoding="utf-8") as f:
                    ruff_data = json.load(f)
                    results["ruff"]["violations"] = len(ruff_data)
                    results["ruff"]["details"] = ruff_data
                    results["ruff"]["success"] = True

        except Exception as e:
            results["ruff"]["error"] = str(e)

        # Run semgrep (if available)
        semgrep_available = self._check_tool_available("semgrep")
        if semgrep_available:
            try:
                semgrep_cmd = (
                    [
                        "semgrep",
                        "--json",
                        "--output",
                        str(artifacts_dir / "semgrep_results.json"),
                        "--config",
                    ]
                    + semgrep_rules
                    + paths
                )

                console.print(f"[blue]Running semgrep: {' '.join(semgrep_cmd)}[/blue]")
                semgrep_result = subprocess.run(
                    semgrep_cmd, capture_output=True, text=True, cwd=working_dir
                )

                # Parse semgrep results
                semgrep_file = artifacts_dir / "semgrep_results.json"
                if semgrep_file.exists():
                    with open(semgrep_file, encoding="utf-8") as f:
                        semgrep_data = json.load(f)
                        results["semgrep"]["violations"] = len(
                            semgrep_data.get("results", [])
                        )
                        results["semgrep"]["details"] = semgrep_data
                        results["semgrep"]["success"] = True

            except Exception as e:
                results["semgrep"]["error"] = str(e)
        else:
            results["semgrep"]["skipped"] = "semgrep not available"

        # Generate summary
        total_violations = (
            results["ruff"]["violations"] + results["semgrep"]["violations"]
        )

        summary = {
            "total_violations": total_violations,
            "max_violations": max_violations,
            "ruff_violations": results["ruff"]["violations"],
            "semgrep_violations": results["semgrep"]["violations"],
            "passed": total_violations <= max_violations,
            "tools_run": {
                "ruff": results["ruff"]["success"],
                "semgrep": results["semgrep"]["success"],
            },
        }

        # Write summary
        with open(artifacts_dir / "lint_summary.json", "w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2)

        # Determine success
        passed = total_violations <= max_violations

        if passed:
            message = f"Code quality check passed: {total_violations} violations (max: {max_violations})"
        else:
            message = f"Code quality check failed: {total_violations} violations (max: {max_violations})"

        artifacts_created = ["lint_summary.json"]
        if results["ruff"]["success"]:
            artifacts_created.append("ruff_results.json")
        if results["semgrep"]["success"]:
            artifacts_created.append("semgrep_results.json")

        return PluginResult(
            plugin_name=self.name,
            passed=passed,
            message=message,
            details=summary,
            artifacts_created=artifacts_created,
        )
