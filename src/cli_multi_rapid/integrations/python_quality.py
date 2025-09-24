"""Python quality tool integrations (ruff, mypy, yamllint, etc.)."""

import logging
from dataclasses import dataclass
from typing import Dict, List, Optional

from .process import ProcessResult, ProcessRunner

logger = logging.getLogger(__name__)


@dataclass
class PythonQualityVersion:
    """Version information for Python quality tools."""

    version: str
    tool: str

    def __str__(self) -> str:
        return f"{self.tool} {self.version}"


class PythonQualityAdapter:
    """Adapter for Python quality tool operations."""

    def __init__(self, runner: ProcessRunner):
        """Initialize Python quality adapter.

        Args:
            runner: ProcessRunner instance
        """
        self.runner = runner

    def version(self) -> PythonQualityVersion:
        """Get Python version information."""
        result = self.runner.run("python --version")
        if result.ok:
            version_str = result.stdout.strip()
            # Extract version from "Python X.Y.Z"
            if "Python" in version_str:
                version_num = version_str.split("Python")[1].strip()
            else:
                version_num = version_str
            return PythonQualityVersion(version=version_num, tool="python")
        else:
            return PythonQualityVersion(version="unknown", tool="python")

    def ruff_check(
        self,
        paths: Optional[List[str]] = None,
        fix: bool = False,
        config: Optional[str] = None,
    ) -> ProcessResult:
        """Run ruff linting.

        Args:
            paths: Paths to check (defaults to current directory)
            fix: Automatically fix issues
            config: Path to ruff config file

        Returns:
            ProcessResult from ruff check
        """
        cmd_parts = ["ruff", "check"]

        if fix:
            cmd_parts.append("--fix")

        if config:
            cmd_parts.extend(["--config", config])

        if paths:
            cmd_parts.extend(paths)
        else:
            cmd_parts.append(".")

        return self.runner.run(" ".join(cmd_parts))

    def ruff_format(
        self,
        paths: Optional[List[str]] = None,
        config: Optional[str] = None,
        check: bool = False,
    ) -> ProcessResult:
        """Run ruff formatting.

        Args:
            paths: Paths to format (defaults to current directory)
            config: Path to ruff config file
            check: Only check formatting, don't modify files

        Returns:
            ProcessResult from ruff format
        """
        cmd_parts = ["ruff", "format"]

        if check:
            cmd_parts.append("--check")

        if config:
            cmd_parts.extend(["--config", config])

        if paths:
            cmd_parts.extend(paths)
        else:
            cmd_parts.append(".")

        return self.runner.run(" ".join(cmd_parts))

    def mypy_check(
        self,
        targets: Optional[List[str]] = None,
        config_file: Optional[str] = None,
        ignore_missing_imports: bool = False,
    ) -> ProcessResult:
        """Run mypy type checking.

        Args:
            targets: Files/directories to check
            config_file: Path to mypy config file
            ignore_missing_imports: Ignore missing import errors

        Returns:
            ProcessResult from mypy
        """
        cmd_parts = ["mypy"]

        if config_file:
            cmd_parts.extend(["--config-file", config_file])

        if ignore_missing_imports:
            cmd_parts.append("--ignore-missing-imports")

        if targets:
            cmd_parts.extend(targets)
        else:
            cmd_parts.append(".")

        return self.runner.run(" ".join(cmd_parts))

    def yamllint_check(
        self,
        paths: Optional[List[str]] = None,
        config: Optional[str] = None,
        format_output: str = "auto",
    ) -> ProcessResult:
        """Run yamllint YAML linting.

        Args:
            paths: Paths to check (defaults to current directory)
            config: Path to yamllint config file
            format_output: Output format (auto, standard, parsable, colored)

        Returns:
            ProcessResult from yamllint
        """
        cmd_parts = ["yamllint"]

        if config:
            cmd_parts.extend(["-c", config])

        cmd_parts.extend(["-f", format_output])

        if paths:
            cmd_parts.extend(paths)
        else:
            cmd_parts.append(".")

        return self.runner.run(" ".join(cmd_parts))

    def markdownlint_check(
        self,
        paths: Optional[List[str]] = None,
        config: Optional[str] = None,
        fix: bool = False,
    ) -> ProcessResult:
        """Run markdownlint for Markdown files.

        Args:
            paths: Paths to check (defaults to current directory)
            config: Path to markdownlint config file
            fix: Automatically fix issues

        Returns:
            ProcessResult from markdownlint
        """
        cmd_parts = ["markdownlint"]

        if config:
            cmd_parts.extend(["-c", config])

        if fix:
            cmd_parts.append("--fix")

        if paths:
            cmd_parts.extend(paths)
        else:
            cmd_parts.append("**/*.md")

        return self.runner.run(" ".join(cmd_parts))

    def detect_secrets_scan(
        self,
        paths: Optional[List[str]] = None,
        baseline: Optional[str] = None,
        exclude_files: Optional[str] = None,
    ) -> ProcessResult:
        """Run detect-secrets to find potential secrets.

        Args:
            paths: Paths to scan (defaults to current directory)
            baseline: Path to baseline file
            exclude_files: Regex pattern for files to exclude

        Returns:
            ProcessResult from detect-secrets
        """
        cmd_parts = ["detect-secrets", "scan"]

        if baseline:
            cmd_parts.extend(["--baseline", baseline])

        if exclude_files:
            cmd_parts.extend(["--exclude-files", exclude_files])

        if paths:
            cmd_parts.extend(paths)
        else:
            cmd_parts.append(".")

        return self.runner.run(" ".join(cmd_parts))

    def detect_secrets_audit(self, baseline: str) -> ProcessResult:
        """Run detect-secrets audit on baseline.

        Args:
            baseline: Path to baseline file

        Returns:
            ProcessResult from detect-secrets audit
        """
        return self.runner.run(f"detect-secrets audit {baseline}")

    def gitleaks_detect(
        self,
        path: Optional[str] = None,
        config: Optional[str] = None,
        verbose: bool = False,
    ) -> ProcessResult:
        """Run gitleaks to detect secrets in git repository.

        Args:
            path: Path to repository (defaults to current directory)
            config: Path to gitleaks config file
            verbose: Enable verbose output

        Returns:
            ProcessResult from gitleaks
        """
        cmd_parts = ["gitleaks", "detect"]

        if path:
            cmd_parts.extend(["--source", path])

        if config:
            cmd_parts.extend(["--config", config])

        if verbose:
            cmd_parts.append("--verbose")

        return self.runner.run(" ".join(cmd_parts))

    def bandit_scan(
        self,
        target: str = ".",
        format_output: str = "json",
        output_file: Optional[str] = None,
        confidence: str = "low",
    ) -> ProcessResult:
        """Run bandit security linting for Python.

        Args:
            target: Target path to scan
            format_output: Output format (json, txt, xml, csv)
            output_file: Output file path
            confidence: Confidence level (high, medium, low)

        Returns:
            ProcessResult from bandit
        """
        cmd_parts = ["bandit", "-r", target]

        cmd_parts.extend(["-f", format_output])
        cmd_parts.extend(["-i", confidence])

        if output_file:
            cmd_parts.extend(["-o", output_file])

        return self.runner.run(" ".join(cmd_parts))

    def semgrep_scan(
        self,
        target: str = ".",
        config: str = "auto",
        output_format: str = "json",
        output_file: Optional[str] = None,
    ) -> ProcessResult:
        """Run semgrep static analysis.

        Args:
            target: Target path to scan
            config: Semgrep config (auto, p/python, etc.)
            output_format: Output format (json, text, sarif)
            output_file: Output file path

        Returns:
            ProcessResult from semgrep
        """
        cmd_parts = ["semgrep", "--config", config, target]

        cmd_parts.extend(
            ["--json" if output_format == "json" else f"--{output_format}"]
        )

        if output_file:
            cmd_parts.extend(["-o", output_file])

        return self.runner.run(" ".join(cmd_parts))

    def run_all(
        self, paths: Optional[List[str]] = None, fix: bool = False
    ) -> Dict[str, ProcessResult]:
        """Run all quality checks.

        Args:
            paths: Paths to check
            fix: Automatically fix issues where possible

        Returns:
            Dictionary mapping tool name to ProcessResult
        """
        results = {}

        # Run ruff
        results["ruff_check"] = self.ruff_check(paths=paths, fix=fix)
        results["ruff_format"] = self.ruff_format(paths=paths)

        # Run mypy
        results["mypy"] = self.mypy_check(targets=paths)

        # Run yamllint
        results["yamllint"] = self.yamllint_check(paths=paths)

        # Run markdownlint
        results["markdownlint"] = self.markdownlint_check(paths=paths, fix=fix)

        # Run detect-secrets
        results["detect_secrets"] = self.detect_secrets_scan(paths=paths)

        # Run gitleaks
        results["gitleaks"] = self.gitleaks_detect()

        return results

    def generate_summary(self, results: Dict[str, ProcessResult]) -> str:
        """Generate summary of quality check results.

        Args:
            results: Dictionary of tool results

        Returns:
            Summary string
        """
        summary_lines = ["Python Quality Check Summary:"]

        for tool, result in results.items():
            status = "✅ PASS" if result.ok else "❌ FAIL"
            summary_lines.append(f"  {tool}: {status}")

            if not result.ok and result.stderr:
                # Add first few lines of error for context
                error_lines = result.stderr.split("\n")[:3]
                for line in error_lines:
                    if line.strip():
                        summary_lines.append(f"    {line.strip()}")

        return "\n".join(summary_lines)


def create_python_quality_adapter(runner: ProcessRunner) -> PythonQualityAdapter:
    """Create a Python quality adapter instance.

    Args:
        runner: ProcessRunner instance

    Returns:
        PythonQualityAdapter instance
    """
    return PythonQualityAdapter(runner)
