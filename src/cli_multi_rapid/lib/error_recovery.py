"""
Intelligent Error Recovery System
Automatically diagnoses and fixes common workflow failures
"""

import json
import logging
import re
import subprocess
from dataclasses import asdict, dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)


class ErrorSeverity(Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class ErrorPattern:
    """Represents a known error pattern and its solution."""

    pattern: str
    severity: ErrorSeverity
    auto_fixable: bool
    fix_strategy: str
    confidence: float


@dataclass
class RecoveryAttempt:
    """Records an error recovery attempt."""

    timestamp: str
    error_type: str
    fix_strategy: str
    success: bool
    details: dict[str, Any]


class IntelligentErrorRecovery:
    """Automatically diagnose and fix workflow errors."""

    def __init__(self):
        self.error_patterns = self._load_error_patterns()
        self.recovery_history: list[RecoveryAttempt] = []

    def _load_error_patterns(self) -> list[ErrorPattern]:
        """Load known error patterns and recovery strategies."""
        return [
            # Python errors
            ErrorPattern(
                pattern=r"ModuleNotFoundError: No module named '(\w+)'",
                severity=ErrorSeverity.MEDIUM,
                auto_fixable=True,
                fix_strategy="install_python_package",
                confidence=0.9,
            ),
            ErrorPattern(
                pattern=r"SyntaxError: invalid syntax",
                severity=ErrorSeverity.HIGH,
                auto_fixable=True,
                fix_strategy="fix_python_syntax",
                confidence=0.8,
            ),
            ErrorPattern(
                pattern=r"ImportError: cannot import name '(\w+)'",
                severity=ErrorSeverity.MEDIUM,
                auto_fixable=True,
                fix_strategy="fix_import_error",
                confidence=0.7,
            ),
            # Git errors
            ErrorPattern(
                pattern=r"error: pathspec '(.+)' did not match any file",
                severity=ErrorSeverity.MEDIUM,
                auto_fixable=True,
                fix_strategy="fix_git_pathspec",
                confidence=0.8,
            ),
            ErrorPattern(
                pattern=r"fatal: not a git repository",
                severity=ErrorSeverity.HIGH,
                auto_fixable=True,
                fix_strategy="initialize_git_repo",
                confidence=0.9,
            ),
            # Tool errors
            ErrorPattern(
                pattern=r"command not found: (.+)",
                severity=ErrorSeverity.HIGH,
                auto_fixable=True,
                fix_strategy="install_missing_tool",
                confidence=0.8,
            ),
            ErrorPattern(
                pattern=r"permission denied",
                severity=ErrorSeverity.MEDIUM,
                auto_fixable=True,
                fix_strategy="fix_permissions",
                confidence=0.7,
            ),
            # Network errors
            ErrorPattern(
                pattern=r"ConnectionError|timeout|network",
                severity=ErrorSeverity.MEDIUM,
                auto_fixable=False,
                fix_strategy="retry_with_backoff",
                confidence=0.6,
            ),
            # File system errors
            ErrorPattern(
                pattern=r"FileNotFoundError: .* '(.+)'",
                severity=ErrorSeverity.MEDIUM,
                auto_fixable=True,
                fix_strategy="create_missing_file",
                confidence=0.8,
            ),
            ErrorPattern(
                pattern=r"PermissionError: .* denied",
                severity=ErrorSeverity.MEDIUM,
                auto_fixable=True,
                fix_strategy="fix_file_permissions",
                confidence=0.7,
            ),
        ]

    def diagnose_error(
        self, error_output: str, context: dict[str, Any] = None
    ) -> Optional[tuple[ErrorPattern, dict[str, Any]]]:
        """Diagnose an error and return the best matching pattern."""
        context = context or {}

        for pattern in self.error_patterns:
            match = re.search(pattern.pattern, error_output, re.IGNORECASE)
            if match:
                logger.info(
                    f"Error pattern matched: {pattern.fix_strategy} (confidence: {pattern.confidence})"
                )

                # Extract details from the match
                details = {
                    "matched_text": match.group(0),
                    "groups": match.groups(),
                    "severity": pattern.severity.value,
                    "auto_fixable": pattern.auto_fixable,
                    "context": context,
                }

                return pattern, details

        logger.warning("No error pattern matched for output")
        return None

    def attempt_recovery(
        self, error_pattern: ErrorPattern, details: dict[str, Any]
    ) -> bool:
        """Attempt to recover from an error using the suggested strategy."""
        strategy = error_pattern.fix_strategy

        logger.info(f"Attempting recovery using strategy: {strategy}")

        try:
            success = self._execute_fix_strategy(strategy, details)

            # Record the attempt
            attempt = RecoveryAttempt(
                timestamp=datetime.utcnow().isoformat(),
                error_type=strategy,
                fix_strategy=strategy,
                success=success,
                details=details,
            )
            self.recovery_history.append(attempt)

            if success:
                logger.info(f"✅ Recovery successful using {strategy}")
            else:
                logger.warning(f"❌ Recovery failed using {strategy}")

            return success

        except Exception as e:
            logger.error(f"Recovery attempt failed with exception: {e}")

            # Record the failed attempt
            attempt = RecoveryAttempt(
                timestamp=datetime.utcnow().isoformat(),
                error_type=strategy,
                fix_strategy=strategy,
                success=False,
                details={**details, "exception": str(e)},
            )
            self.recovery_history.append(attempt)

            return False

    def _execute_fix_strategy(self, strategy: str, details: dict[str, Any]) -> bool:
        """Execute a specific fix strategy."""

        if strategy == "install_python_package":
            return self._install_python_package(details)
        elif strategy == "fix_python_syntax":
            return self._fix_python_syntax(details)
        elif strategy == "fix_import_error":
            return self._fix_import_error(details)
        elif strategy == "fix_git_pathspec":
            return self._fix_git_pathspec(details)
        elif strategy == "initialize_git_repo":
            return self._initialize_git_repo(details)
        elif strategy == "install_missing_tool":
            return self._install_missing_tool(details)
        elif strategy == "fix_permissions":
            return self._fix_permissions(details)
        elif strategy == "retry_with_backoff":
            return self._retry_with_backoff(details)
        elif strategy == "create_missing_file":
            return self._create_missing_file(details)
        elif strategy == "fix_file_permissions":
            return self._fix_file_permissions(details)
        else:
            logger.warning(f"Unknown fix strategy: {strategy}")
            return False

    def _install_python_package(self, details: dict[str, Any]) -> bool:
        """Install missing Python package."""
        if details.get("groups"):
            package_name = details["groups"][0]
            try:
                result = subprocess.run(
                    ["pip", "install", package_name],
                    capture_output=True,
                    text=True,
                    timeout=300,
                )
                return result.returncode == 0
            except Exception:
                return False
        return False

    def _fix_python_syntax(self, details: dict[str, Any]) -> bool:
        """Attempt to fix Python syntax errors (placeholder)."""
        # This would integrate with a code formatter or linter
        logger.info("Python syntax fix would require code analysis")
        return False

    def _fix_import_error(self, details: dict[str, Any]) -> bool:
        """Fix import errors by suggesting alternatives."""
        logger.info("Import error fix would require dependency analysis")
        return False

    def _fix_git_pathspec(self, details: dict[str, Any]) -> bool:
        """Fix git pathspec errors."""
        if details.get("groups"):
            pathspec = details["groups"][0]
            # Could suggest similar files or create the missing path
            logger.info(
                f"Git pathspec '{pathspec}' not found - would suggest alternatives"
            )
        return False

    def _initialize_git_repo(self, details: dict[str, Any]) -> bool:
        """Initialize git repository."""
        try:
            result = subprocess.run(
                ["git", "init"], capture_output=True, text=True, timeout=30
            )
            return result.returncode == 0
        except Exception:
            return False

    def _install_missing_tool(self, details: dict[str, Any]) -> bool:
        """Install missing command-line tool."""
        if details.get("groups"):
            tool_name = details["groups"][0]
            logger.info(f"Would attempt to install missing tool: {tool_name}")
            # This would integrate with package managers (apt, brew, choco, etc.)
        return False

    def _fix_permissions(self, details: dict[str, Any]) -> bool:
        """Fix file permissions."""
        logger.info("Permission fix would require elevated privileges")
        return False

    def _retry_with_backoff(self, details: dict[str, Any]) -> bool:
        """Retry operation with exponential backoff."""
        logger.info("Would retry operation with backoff strategy")
        return False

    def _create_missing_file(self, details: dict[str, Any]) -> bool:
        """Create missing file or directory."""
        if details.get("groups"):
            file_path = details["groups"][0]
            try:
                Path(file_path).parent.mkdir(parents=True, exist_ok=True)
                Path(file_path).touch()
                return True
            except Exception:
                return False
        return False

    def _fix_file_permissions(self, details: dict[str, Any]) -> bool:
        """Fix file permission errors."""
        logger.info("File permission fix would require system calls")
        return False

    def get_recovery_stats(self) -> dict[str, Any]:
        """Get statistics about recovery attempts."""
        if not self.recovery_history:
            return {"total_attempts": 0, "success_rate": 0.0}

        total = len(self.recovery_history)
        successful = sum(1 for attempt in self.recovery_history if attempt.success)

        strategies = {}
        for attempt in self.recovery_history:
            strategy = attempt.fix_strategy
            if strategy not in strategies:
                strategies[strategy] = {"total": 0, "successful": 0}
            strategies[strategy]["total"] += 1
            if attempt.success:
                strategies[strategy]["successful"] += 1

        return {
            "total_attempts": total,
            "successful_attempts": successful,
            "success_rate": successful / total,
            "strategy_stats": strategies,
            "recent_attempts": [
                asdict(attempt) for attempt in self.recovery_history[-5:]
            ],
        }

    def save_recovery_history(self, file_path: Path):
        """Save recovery history to file."""
        history_data = {
            "recovery_history": [asdict(attempt) for attempt in self.recovery_history],
            "stats": self.get_recovery_stats(),
        }

        with open(file_path, "w") as f:
            json.dump(history_data, f, indent=2)

    def load_recovery_history(self, file_path: Path):
        """Load recovery history from file."""
        if not file_path.exists():
            return

        try:
            with open(file_path) as f:
                data = json.load(f)

            self.recovery_history = [
                RecoveryAttempt(**attempt_data)
                for attempt_data in data.get("recovery_history", [])
            ]
        except Exception as e:
            logger.warning(f"Failed to load recovery history: {e}")


# Example usage and testing
def example_usage():
    """Example of how to use the error recovery system."""
    recovery = IntelligentErrorRecovery()

    # Simulate different types of errors
    test_errors = [
        "ModuleNotFoundError: No module named 'requests'",
        "SyntaxError: invalid syntax at line 42",
        "fatal: not a git repository (or any of the parent directories): .git",
        "FileNotFoundError: [Errno 2] No such file or directory: 'config.json'",
        "command not found: docker",
    ]

    for error_output in test_errors:
        print(f"\n🔍 Analyzing error: {error_output}")

        result = recovery.diagnose_error(error_output)
        if result:
            pattern, details = result
            print(f"  📋 Diagnosed as: {pattern.fix_strategy}")
            print(f"  🎯 Confidence: {pattern.confidence}")
            print(f"  ⚡ Auto-fixable: {pattern.auto_fixable}")

            if pattern.auto_fixable:
                success = recovery.attempt_recovery(pattern, details)
                print(f"  🔧 Recovery {'✅ succeeded' if success else '❌ failed'}")

    # Show recovery statistics
    stats = recovery.get_recovery_stats()
    print("\n📊 Recovery Statistics:")
    print(f"  Total attempts: {stats['total_attempts']}")
    print(f"  Success rate: {stats['success_rate']:.1%}")


if __name__ == "__main__":
    example_usage()
