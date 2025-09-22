#!/usr/bin/env python3
"""
VS Code Diagnostics Adapter

Runs diagnostic analysis using common development tools:
- ruff: Python linting and analysis
- mypy: Python type checking
- pylint: Additional Python analysis
- eslint: JavaScript/TypeScript linting (if available)

Generates structured diagnostic reports compatible with workflow gates.
"""

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any, Optional

from .base_adapter import AdapterResult, AdapterType, BaseAdapter


class VSCodeDiagnosticsAdapter(BaseAdapter):
    """Adapter for running diagnostic analysis tools."""

    def __init__(self):
        super().__init__(
            name="vscode_diagnostics",
            adapter_type=AdapterType.DETERMINISTIC,
            description="Run VS Code diagnostic analysis (linting, type checking)",
        )
        self._available_analyzers = self._check_available_analyzers()

    def _check_available_analyzers(self) -> dict[str, bool]:
        """Check which diagnostic tools are available."""
        analyzers = {}
        tools = ["ruff", "mypy", "pylint", "eslint", "tsc"]

        for tool in tools:
            analyzers[tool] = shutil.which(tool) is not None
            if analyzers[tool]:
                self.logger.debug(f"Found {tool}: {shutil.which(tool)}")

        # Always consider "python" analyzer available if Python files exist
        analyzers["python"] = True
        return analyzers

    def is_available(self) -> bool:
        """Check if at least one analyzer is available."""
        return any(self._available_analyzers.values())

    def validate_step(self, step: dict[str, Any]) -> bool:
        """Validate that this adapter can execute the given step."""
        if not self.is_available():
            return False

        # Check if requested analyzers are available
        with_params = self._extract_with_params(step)
        requested_analyzers = with_params.get("analyzers", ["python"])

        return any(
            self._available_analyzers.get(analyzer, False)
            for analyzer in requested_analyzers
        )

    def estimate_cost(self, step: dict[str, Any]) -> int:
        """Estimate token cost (0 for deterministic tools)."""
        return 0

    def execute(
        self,
        step: dict[str, Any],
        context: Optional[dict[str, Any]] = None,
        files: Optional[str] = None,
    ) -> AdapterResult:
        """Execute diagnostic analysis on specified files."""
        self._log_execution_start(step)

        with_params = self._extract_with_params(step)
        emit_paths = self._extract_emit_paths(step)

        # Determine which analyzers to run
        requested_analyzers = with_params.get("analyzers", ["python"])
        severity_filter = with_params.get(
            "min_severity", "info"
        )  # error, warning, info

        # Determine target files
        if not files:
            files = with_params.get("files", "**/*.py")

        # Resolve file patterns by language
        target_files = self._resolve_files_by_language(files, requested_analyzers)

        if not any(target_files.values()):
            return AdapterResult(
                success=True,
                output="No files found for diagnostic analysis",
                artifacts=emit_paths,
            )

        # Run analyzers
        results = {}
        total_issues = 0
        errors = []

        for analyzer in requested_analyzers:
            if not self._available_analyzers.get(analyzer, False):
                self.logger.warning(f"Skipping {analyzer}: not available")
                continue

            try:
                analyzer_result = self._run_analyzer(
                    analyzer, target_files, with_params
                )
                results[analyzer] = analyzer_result

                issues = analyzer_result.get("issues", [])
                filtered_issues = self._filter_by_severity(issues, severity_filter)
                total_issues += len(filtered_issues)

                if analyzer_result.get("error"):
                    errors.append(f"{analyzer}: {analyzer_result['error']}")

            except Exception as e:
                error_msg = f"Failed to run {analyzer}: {e}"
                self.logger.error(error_msg)
                errors.append(error_msg)

        # Generate artifacts
        artifacts = self._generate_artifacts(emit_paths, results, target_files)

        # Determine success (no errors from analyzer execution)
        success = len(errors) == 0
        output = self._format_output(results, total_issues, target_files)
        error = "; ".join(errors) if errors else None

        result = AdapterResult(
            success=success,
            output=output,
            error=error,
            artifacts=artifacts,
            metadata={
                "analyzers_run": list(results.keys()),
                "total_issues": total_issues,
                "files_analyzed": sum(len(files) for files in target_files.values()),
                "results": results,
            },
        )

        self._log_execution_complete(result)
        return result

    def _resolve_files_by_language(
        self, pattern: str, analyzers: list[str]
    ) -> dict[str, list[Path]]:
        """Resolve file patterns to files grouped by language."""
        files_by_lang = {"python": [], "javascript": [], "typescript": []}

        try:
            current_dir = Path(".")

            # Resolve glob pattern
            if "**" in pattern:
                all_files = list(current_dir.glob(pattern))
            else:
                all_files = list(current_dir.glob(pattern))

            # Group by file type
            for file_path in all_files:
                if not file_path.is_file():
                    continue

                suffix = file_path.suffix.lower()
                if suffix == ".py":
                    files_by_lang["python"].append(file_path)
                elif suffix in [".js", ".jsx"]:
                    files_by_lang["javascript"].append(file_path)
                elif suffix in [".ts", ".tsx"]:
                    files_by_lang["typescript"].append(file_path)

            # Log results
            for lang, files in files_by_lang.items():
                if files:
                    self.logger.debug(f"Found {len(files)} {lang} files")

            return files_by_lang

        except Exception as e:
            self.logger.error(f"Failed to resolve file pattern {pattern}: {e}")
            return {"python": [], "javascript": [], "typescript": []}

    def _run_analyzer(
        self, analyzer: str, target_files: dict[str, list[Path]], params: dict[str, Any]
    ) -> dict[str, Any]:
        """Run a specific diagnostic analyzer."""
        if analyzer == "python" or analyzer == "ruff":
            return self._run_ruff(target_files["python"])
        elif analyzer == "mypy":
            return self._run_mypy(target_files["python"])
        elif analyzer == "pylint":
            return self._run_pylint(target_files["python"])
        elif analyzer == "eslint":
            js_files = target_files["javascript"] + target_files["typescript"]
            return self._run_eslint(js_files)
        else:
            return {"error": f"Unknown analyzer: {analyzer}"}

    def _run_ruff(self, files: list[Path]) -> dict[str, Any]:
        """Run ruff linter."""
        if not files:
            return {"issues": [], "exit_code": 0}

        try:
            file_paths = [str(f) for f in files]
            cmd = ["ruff", "check", "--output-format=json"] + file_paths

            result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)

            issues = []
            if result.stdout:
                try:
                    ruff_output = json.loads(result.stdout)
                    for issue in ruff_output:
                        issues.append(
                            {
                                "file": issue.get("filename", ""),
                                "line": issue.get("location", {}).get("row", 1),
                                "column": issue.get("location", {}).get("column", 1),
                                "severity": "warning",  # Ruff issues are generally warnings
                                "code": issue.get("code", ""),
                                "message": issue.get("message", ""),
                                "rule": issue.get("code", ""),
                                "source": "ruff",
                            }
                        )
                except json.JSONDecodeError:
                    self.logger.warning("Failed to parse ruff JSON output")

            return {
                "exit_code": result.returncode,
                "issues": issues,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "error": result.stderr if result.returncode > 1 else None,
            }

        except subprocess.TimeoutExpired:
            return {"error": "ruff execution timed out"}
        except Exception as e:
            return {"error": str(e)}

    def _run_mypy(self, files: list[Path]) -> dict[str, Any]:
        """Run mypy type checker."""
        if not files:
            return {"issues": [], "exit_code": 0}

        try:
            file_paths = [str(f) for f in files]
            cmd = ["mypy", "--show-error-codes"] + file_paths

            result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)

            # Parse mypy output (format: file:line:column: severity: message [code])
            issues = []
            for line in result.stdout.splitlines():
                if ":" in line and (
                    " error:" in line or " warning:" in line or " note:" in line
                ):
                    parts = line.split(":", 3)
                    if len(parts) >= 4:
                        file_path = parts[0]
                        line_num = parts[1]
                        col_num = parts[2] if parts[2].isdigit() else "1"
                        message_part = parts[3].strip()

                        # Extract severity
                        severity = "info"
                        if " error:" in message_part:
                            severity = "error"
                        elif " warning:" in message_part:
                            severity = "warning"

                        # Extract message and code
                        message = message_part
                        code = ""
                        if "[" in message and "]" in message:
                            code_start = message.rfind("[")
                            code = message[code_start + 1 : -1]
                            message = message[:code_start].strip()

                        issues.append(
                            {
                                "file": file_path,
                                "line": int(line_num) if line_num.isdigit() else 1,
                                "column": int(col_num) if col_num.isdigit() else 1,
                                "severity": severity,
                                "code": code,
                                "message": message,
                                "rule": code,
                                "source": "mypy",
                            }
                        )

            return {
                "exit_code": result.returncode,
                "issues": issues,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "error": result.stderr if result.returncode > 1 else None,
            }

        except subprocess.TimeoutExpired:
            return {"error": "mypy execution timed out"}
        except Exception as e:
            return {"error": str(e)}

    def _run_pylint(self, files: list[Path]) -> dict[str, Any]:
        """Run pylint analyzer."""
        if not files:
            return {"issues": [], "exit_code": 0}

        try:
            file_paths = [str(f) for f in files]
            cmd = ["pylint", "--output-format=json"] + file_paths

            result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)

            issues = []
            if result.stdout:
                try:
                    pylint_output = json.loads(result.stdout)
                    for issue in pylint_output:
                        issues.append(
                            {
                                "file": issue.get("path", ""),
                                "line": issue.get("line", 1),
                                "column": issue.get("column", 1),
                                "severity": issue.get("type", "info").lower(),
                                "code": issue.get("symbol", ""),
                                "message": issue.get("message", ""),
                                "rule": issue.get("symbol", ""),
                                "source": "pylint",
                            }
                        )
                except json.JSONDecodeError:
                    self.logger.warning("Failed to parse pylint JSON output")

            return {
                "exit_code": result.returncode,
                "issues": issues,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "error": (
                    result.stderr if result.returncode > 2 else None
                ),  # pylint exit codes
            }

        except subprocess.TimeoutExpired:
            return {"error": "pylint execution timed out"}
        except Exception as e:
            return {"error": str(e)}

    def _run_eslint(self, files: list[Path]) -> dict[str, Any]:
        """Run eslint analyzer."""
        if not files:
            return {"issues": [], "exit_code": 0}

        try:
            file_paths = [str(f) for f in files]
            cmd = ["eslint", "--format=json"] + file_paths

            result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)

            issues = []
            if result.stdout:
                try:
                    eslint_output = json.loads(result.stdout)
                    for file_result in eslint_output:
                        for issue in file_result.get("messages", []):
                            severity_map = {1: "warning", 2: "error"}
                            issues.append(
                                {
                                    "file": file_result.get("filePath", ""),
                                    "line": issue.get("line", 1),
                                    "column": issue.get("column", 1),
                                    "severity": severity_map.get(
                                        issue.get("severity", 1), "warning"
                                    ),
                                    "code": issue.get("ruleId", ""),
                                    "message": issue.get("message", ""),
                                    "rule": issue.get("ruleId", ""),
                                    "source": "eslint",
                                }
                            )
                except json.JSONDecodeError:
                    self.logger.warning("Failed to parse eslint JSON output")

            return {
                "exit_code": result.returncode,
                "issues": issues,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "error": result.stderr if result.returncode > 2 else None,
            }

        except subprocess.TimeoutExpired:
            return {"error": "eslint execution timed out"}
        except Exception as e:
            return {"error": str(e)}

    def _filter_by_severity(self, issues: list[dict], min_severity: str) -> list[dict]:
        """Filter issues by minimum severity level."""
        severity_levels = {"info": 0, "warning": 1, "error": 2}
        min_level = severity_levels.get(min_severity.lower(), 0)

        return [
            issue
            for issue in issues
            if severity_levels.get(issue.get("severity", "info"), 0) >= min_level
        ]

    def _generate_artifacts(
        self,
        emit_paths: list[str],
        results: dict[str, Any],
        target_files: dict[str, list[Path]],
    ) -> list[str]:
        """Generate diagnostic artifacts."""
        artifacts = []

        for emit_path in emit_paths:
            try:
                # Collect all issues
                all_issues = []
                for analyzer_result in results.values():
                    all_issues.extend(analyzer_result.get("issues", []))

                # Group issues by type for easy querying
                issues_by_type = {}
                for issue in all_issues:
                    severity = issue.get("severity", "info")
                    if severity not in issues_by_type:
                        issues_by_type[severity] = []
                    issues_by_type[severity].append(issue)

                artifact_data = {
                    "adapter": "vscode_diagnostics",
                    "timestamp": "2025-09-20T12:00:00Z",
                    "files_analyzed": {
                        lang: [str(f) for f in files]
                        for lang, files in target_files.items()
                    },
                    "analyzers": list(results.keys()),
                    "summary": {
                        "total_issues": len(all_issues),
                        "by_severity": {
                            severity: len(issues)
                            for severity, issues in issues_by_type.items()
                        },
                    },
                    "issues": all_issues,
                    "results": results,
                }

                # Ensure directory exists
                Path(emit_path).parent.mkdir(parents=True, exist_ok=True)

                # Write artifact
                with open(emit_path, "w") as f:
                    json.dump(artifact_data, f, indent=2)

                artifacts.append(emit_path)
                self.logger.debug(f"Generated artifact: {emit_path}")

            except Exception as e:
                self.logger.error(f"Failed to generate artifact {emit_path}: {e}")

        return artifacts

    def _format_output(
        self,
        results: dict[str, Any],
        total_issues: int,
        target_files: dict[str, list[Path]],
    ) -> str:
        """Format human-readable output summary."""
        total_files = sum(len(files) for files in target_files.values())

        lines = [
            f"VS Code Diagnostics: {total_files} files analyzed",
            f"Total issues found: {total_issues}",
            "",
        ]

        for analyzer, result in results.items():
            issues = result.get("issues", [])
            status = "OK" if not result.get("error") else "FAIL"
            lines.append(f"{status} {analyzer}: {len(issues)} issues")

            if result.get("error"):
                lines.append(f"   Error: {result['error']}")

        # Add severity breakdown
        if total_issues > 0:
            lines.append("")
            lines.append("Issue breakdown:")

            severity_counts = {"error": 0, "warning": 0, "info": 0}
            for result in results.values():
                for issue in result.get("issues", []):
                    severity = issue.get("severity", "info")
                    if severity in severity_counts:
                        severity_counts[severity] += 1

            for severity, count in severity_counts.items():
                if count > 0:
                    icon = {"error": "ERR", "warning": "WARN", "info": "INFO"}[severity]
                    lines.append(f"  {icon} {severity.title()}: {count}")

        return "\n".join(lines)
