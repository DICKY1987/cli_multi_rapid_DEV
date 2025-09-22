#!/usr/bin/env python3
"""
Pytest Runner Adapter

Executes Python tests using pytest with coverage reporting and result parsing.
Supports various pytest configurations and generates structured test reports.
"""

import json
import shutil
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Optional

from .base_adapter import AdapterResult, AdapterType, BaseAdapter


class PytestRunnerAdapter(BaseAdapter):
    """Adapter for running Python tests with pytest."""

    def __init__(self):
        super().__init__(
            name="pytest_runner",
            adapter_type=AdapterType.DETERMINISTIC,
            description="Execute Python tests with coverage reporting",
        )

    def is_available(self) -> bool:
        """Check if pytest is available."""
        return shutil.which("pytest") is not None

    def validate_step(self, step: dict[str, Any]) -> bool:
        """Validate that this adapter can execute the given step."""
        return self.is_available()

    def estimate_cost(self, step: dict[str, Any]) -> int:
        """Estimate token cost (0 for deterministic tools)."""
        return 0

    def execute(
        self,
        step: dict[str, Any],
        context: Optional[dict[str, Any]] = None,
        files: Optional[str] = None,
    ) -> AdapterResult:
        """Execute pytest with specified configuration."""
        self._log_execution_start(step)

        with_params = self._extract_with_params(step)
        emit_paths = self._extract_emit_paths(step)

        # Extract pytest configuration
        test_path = with_params.get("test_path", "tests/")
        coverage = with_params.get("coverage", True)
        coverage_threshold = with_params.get("coverage_threshold", 80)
        pytest_args = with_params.get("args", [])
        include_slow_tests = with_params.get("include_slow", False)

        # Build pytest command
        cmd = ["pytest"]

        # Add test path
        if Path(test_path).exists():
            cmd.append(test_path)
        else:
            # If test path doesn't exist, try to find tests
            test_dirs = ["tests/", "test/", "."]
            found_tests = False
            for test_dir in test_dirs:
                if Path(test_dir).exists() and list(Path(test_dir).glob("test_*.py")):
                    cmd.append(test_dir)
                    found_tests = True
                    break

            if not found_tests:
                return AdapterResult(
                    success=False,
                    error=f"No tests found in {test_path} or default locations",
                    artifacts=emit_paths,
                )

        # Add coverage if requested
        if coverage:
            cmd.extend(["--cov=.", "--cov-report=xml", "--cov-report=term"])

        # Add verbose output and XML reporting
        cmd.extend(["-v", "--tb=short", "--junit-xml=test-results.xml"])

        # Add custom arguments
        cmd.extend(pytest_args)

        # Skip slow tests unless requested
        if not include_slow_tests:
            cmd.extend(["-m", "not slow"])

        try:
            self.logger.info(f"Running pytest: {' '.join(cmd)}")
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300,  # 5 minute timeout
                cwd=".",
            )

            # Parse test results
            test_results = self._parse_test_results()
            coverage_results = self._parse_coverage_results() if coverage else None

            # Check coverage threshold
            coverage_passed = True
            if coverage and coverage_results:
                total_coverage = coverage_results.get("total_coverage", 0)
                coverage_passed = total_coverage >= coverage_threshold

            # Generate artifacts
            artifacts = self._generate_artifacts(
                emit_paths, test_results, coverage_results, result
            )

            # Determine success
            tests_passed = result.returncode == 0
            success = tests_passed and coverage_passed

            # Format output
            output = self._format_output(
                result, test_results, coverage_results, coverage_threshold
            )

            # Compile errors
            errors = []
            if not tests_passed:
                errors.append("Some tests failed")
            if not coverage_passed:
                errors.append(
                    f"Coverage {coverage_results.get('total_coverage', 0):.1f}% below threshold {coverage_threshold}%"
                )

            return AdapterResult(
                success=success,
                output=output,
                error="; ".join(errors) if errors else None,
                artifacts=artifacts,
                metadata={
                    "tests_run": test_results.get("total", 0),
                    "tests_passed": test_results.get("passed", 0),
                    "tests_failed": test_results.get("failed", 0),
                    "coverage": (
                        coverage_results.get("total_coverage")
                        if coverage_results
                        else None
                    ),
                    "exit_code": result.returncode,
                },
            )

        except subprocess.TimeoutExpired:
            return AdapterResult(
                success=False,
                error="Test execution timed out (5 minutes)",
                artifacts=emit_paths,
            )
        except Exception as e:
            return AdapterResult(
                success=False, error=f"Failed to run tests: {e}", artifacts=emit_paths
            )

    def _parse_test_results(self) -> dict[str, Any]:
        """Parse pytest XML results."""
        xml_file = Path("test-results.xml")
        if not xml_file.exists():
            self.logger.warning("No test results XML found")
            return {"total": 0, "passed": 0, "failed": 0, "errors": 0, "skipped": 0}

        try:
            tree = ET.parse(xml_file)
            root = tree.getroot()

            # Extract test statistics
            total = int(root.get("tests", 0))
            failures = int(root.get("failures", 0))
            errors = int(root.get("errors", 0))
            skipped = int(root.get("skipped", 0))
            passed = total - failures - errors - skipped

            # Extract individual test results
            test_cases = []
            for testcase in root.findall(".//testcase"):
                case_data = {
                    "name": testcase.get("name"),
                    "classname": testcase.get("classname"),
                    "time": float(testcase.get("time", 0)),
                    "status": "passed",
                }

                # Check for failures or errors
                if testcase.find("failure") is not None:
                    case_data["status"] = "failed"
                    case_data["failure"] = testcase.find("failure").text
                elif testcase.find("error") is not None:
                    case_data["status"] = "error"
                    case_data["error"] = testcase.find("error").text
                elif testcase.find("skipped") is not None:
                    case_data["status"] = "skipped"
                    case_data["skip_reason"] = testcase.find("skipped").get(
                        "message", ""
                    )

                test_cases.append(case_data)

            return {
                "total": total,
                "passed": passed,
                "failed": failures,
                "errors": errors,
                "skipped": skipped,
                "duration": float(root.get("time", 0)),
                "test_cases": test_cases,
            }

        except ET.ParseError as e:
            self.logger.error(f"Failed to parse test results XML: {e}")
            return {"total": 0, "passed": 0, "failed": 0, "errors": 0, "skipped": 0}
        except Exception as e:
            self.logger.error(f"Error processing test results: {e}")
            return {"total": 0, "passed": 0, "failed": 0, "errors": 0, "skipped": 0}

    def _parse_coverage_results(self) -> Optional[dict[str, Any]]:
        """Parse coverage XML results."""
        xml_file = Path("coverage.xml")
        if not xml_file.exists():
            self.logger.warning("No coverage XML found")
            return None

        try:
            tree = ET.parse(xml_file)
            root = tree.getroot()

            # Extract overall coverage
            total_coverage = 0
            if root.get("line-rate"):
                total_coverage = float(root.get("line-rate")) * 100

            # Extract file-level coverage
            files = []
            for package in root.findall(".//package"):
                for cls in package.findall(".//class"):
                    file_coverage = float(cls.get("line-rate", 0)) * 100
                    files.append(
                        {
                            "filename": cls.get("filename"),
                            "coverage": file_coverage,
                            "lines_covered": int(cls.get("lines-covered", 0)),
                            "lines_valid": int(cls.get("lines-valid", 1)),
                        }
                    )

            return {
                "total_coverage": total_coverage,
                "files": files,
                "lines_covered": int(root.get("lines-covered", 0)),
                "lines_valid": int(root.get("lines-valid", 1)),
            }

        except ET.ParseError as e:
            self.logger.error(f"Failed to parse coverage XML: {e}")
            return None
        except Exception as e:
            self.logger.error(f"Error processing coverage results: {e}")
            return None

    def _generate_artifacts(
        self,
        emit_paths: list[str],
        test_results: dict[str, Any],
        coverage_results: Optional[dict[str, Any]],
        subprocess_result: subprocess.CompletedProcess,
    ) -> list[str]:
        """Generate artifact files with test and coverage results."""
        artifacts = []

        for emit_path in emit_paths:
            try:
                artifact_data = {
                    "adapter": "pytest_runner",
                    "timestamp": "2025-09-20T12:00:00Z",  # Would be actual timestamp
                    "test_results": test_results,
                    "coverage_results": coverage_results,
                    "command": (
                        subprocess_result.args
                        if hasattr(subprocess_result, "args")
                        else []
                    ),
                    "exit_code": subprocess_result.returncode,
                    "stdout": subprocess_result.stdout,
                    "stderr": subprocess_result.stderr,
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
        subprocess_result: subprocess.CompletedProcess,
        test_results: dict[str, Any],
        coverage_results: Optional[dict[str, Any]],
        coverage_threshold: int,
    ) -> str:
        """Format human-readable output summary."""
        lines = ["=== Pytest Execution Results ===", ""]

        # Test summary
        total = test_results.get("total", 0)
        passed = test_results.get("passed", 0)
        failed = test_results.get("failed", 0)
        errors = test_results.get("errors", 0)
        skipped = test_results.get("skipped", 0)

        lines.extend(
            [
                f"Tests run: {total}",
                f"PASS: {passed}",
                f"FAIL: {failed}",
                f"ERROR: {errors}",
                f"SKIP: {skipped}",
                "",
            ]
        )

        # Coverage summary
        if coverage_results:
            total_cov = coverage_results.get("total_coverage", 0)
            cov_status = "OK" if total_cov >= coverage_threshold else "FAIL"
            lines.extend(
                [
                    f"{cov_status} Coverage: {total_cov:.1f}% (threshold: {coverage_threshold}%)",
                    "",
                ]
            )

        # Add failed test details if any
        if failed > 0 or errors > 0:
            lines.append("Failed Tests:")
            for test_case in test_results.get("test_cases", []):
                if test_case["status"] in ["failed", "error"]:
                    lines.append(
                        f"  FAIL: {test_case['classname']}::{test_case['name']}"
                    )

        return "\n".join(lines)
