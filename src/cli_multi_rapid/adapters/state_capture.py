#!/usr/bin/env python3
"""
State Capture Adapter

Captures baseline repository state including file checksums, git hash,
dependency locks, and test baseline for rollback and verification purposes.
"""

import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any, Dict, Optional

from .base_adapter import AdapterResult, AdapterType, BaseAdapter


class StateCaptureAdapter(BaseAdapter):
    """Adapter for capturing repository baseline state."""

    def __init__(self):
        super().__init__(
            name="state_capture",
            adapter_type=AdapterType.DETERMINISTIC,
            description="Capture repository baseline state with checksums and git info",
        )

    def execute(
        self,
        step: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None,
        files: Optional[str] = None,
    ) -> AdapterResult:
        """Execute state capture."""
        self._log_execution_start(step)

        try:
            with_params = self._extract_with_params(step)
            repository_scan = with_params.get("repository_scan", True)
            file_checksums = with_params.get("file_checksums", True)
            dependency_lock = with_params.get("dependency_lock", True)
            test_baseline = with_params.get("test_baseline", True)

            baseline_state = {
                "capture_timestamp": self._get_timestamp(),
                "working_directory": str(Path.cwd()),
                "scan_parameters": {
                    "repository_scan": repository_scan,
                    "file_checksums": file_checksums,
                    "dependency_lock": dependency_lock,
                    "test_baseline": test_baseline,
                }
            }

            # Capture git repository information
            if repository_scan:
                git_info = self._capture_git_info()
                baseline_state["git"] = git_info

            # Generate file checksums
            if file_checksums:
                checksums = self._generate_file_checksums()
                baseline_state["file_checksums"] = checksums

            # Capture dependency information
            if dependency_lock:
                dependencies = self._capture_dependencies()
                baseline_state["dependencies"] = dependencies

            # Capture test baseline
            if test_baseline:
                test_info = self._capture_test_baseline()
                baseline_state["test_baseline"] = test_info

            # Write baseline state artifact
            emit_paths = self._extract_emit_paths(step)
            artifacts = []

            if emit_paths:
                for emit_path in emit_paths:
                    artifact_path = Path(emit_path)
                    artifact_path.parent.mkdir(parents=True, exist_ok=True)

                    with open(artifact_path, 'w', encoding='utf-8') as f:
                        json.dump(baseline_state, f, indent=2)

                    artifacts.append(str(artifact_path))
                    self.logger.info(f"Baseline state written to: {artifact_path}")

            result = AdapterResult(
                success=True,
                tokens_used=0,  # Deterministic operation
                artifacts=artifacts,
                output=f"Captured baseline state with {len(baseline_state.get('file_checksums', {}))} file checksums",
                metadata=baseline_state
            )

            self._log_execution_complete(result)
            return result

        except Exception as e:
            error_msg = f"State capture failed: {str(e)}"
            self.logger.error(error_msg)
            return AdapterResult(
                success=False,
                error=error_msg,
                metadata={"exception_type": type(e).__name__}
            )

    def validate_step(self, step: Dict[str, Any]) -> bool:
        """Validate that this adapter can execute the given step."""
        # Basic validation - this adapter has flexible parameters
        return True

    def estimate_cost(self, step: Dict[str, Any]) -> int:
        """Estimate token cost (0 for deterministic operations)."""
        return 0

    def is_available(self) -> bool:
        """Check if git is available."""
        try:
            result = subprocess.run(
                ["git", "--version"],
                capture_output=True,
                text=True,
                timeout=5
            )
            return result.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return False

    def _capture_git_info(self) -> Dict[str, Any]:
        """Capture git repository information."""
        git_info = {}

        try:
            # Get current commit hash
            result = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                capture_output=True,
                text=True,
                timeout=10
            )
            if result.returncode == 0:
                git_info["commit_hash"] = result.stdout.strip()

            # Get branch name
            result = subprocess.run(
                ["git", "branch", "--show-current"],
                capture_output=True,
                text=True,
                timeout=10
            )
            if result.returncode == 0:
                git_info["branch"] = result.stdout.strip()

            # Get remote origin URL
            result = subprocess.run(
                ["git", "remote", "get-url", "origin"],
                capture_output=True,
                text=True,
                timeout=10
            )
            if result.returncode == 0:
                git_info["remote_url"] = result.stdout.strip()

            # Check for uncommitted changes
            result = subprocess.run(
                ["git", "status", "--porcelain"],
                capture_output=True,
                text=True,
                timeout=10
            )
            git_info["has_uncommitted_changes"] = len(result.stdout.strip()) > 0
            if git_info["has_uncommitted_changes"]:
                git_info["uncommitted_files"] = result.stdout.strip().split('\n')

        except Exception as e:
            self.logger.warning(f"Failed to capture some git info: {e}")

        return git_info

    def _generate_file_checksums(self) -> Dict[str, str]:
        """Generate SHA256 checksums for all tracked files."""
        checksums = {}

        try:
            # Get list of tracked files
            result = subprocess.run(
                ["git", "ls-files"],
                capture_output=True,
                text=True,
                timeout=30
            )

            if result.returncode == 0:
                tracked_files = result.stdout.strip().split('\n')

                for file_path in tracked_files:
                    if file_path.strip():  # Skip empty lines
                        try:
                            full_path = Path(file_path)
                            if full_path.exists() and full_path.is_file():
                                checksums[file_path] = self._calculate_file_checksum(full_path)
                        except Exception as e:
                            self.logger.warning(f"Failed to checksum {file_path}: {e}")

        except Exception as e:
            self.logger.warning(f"Failed to generate checksums: {e}")

        return checksums

    def _calculate_file_checksum(self, file_path: Path) -> str:
        """Calculate SHA256 checksum for a file."""
        sha256_hash = hashlib.sha256()
        with open(file_path, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()

    def _capture_dependencies(self) -> Dict[str, Any]:
        """Capture dependency information from various lock files."""
        dependencies = {}

        # Check for Python dependencies
        for lockfile in ["requirements.txt", "Pipfile.lock", "poetry.lock", "pyproject.toml"]:
            lockfile_path = Path(lockfile)
            if lockfile_path.exists():
                dependencies[lockfile] = {
                    "exists": True,
                    "checksum": self._calculate_file_checksum(lockfile_path),
                    "size": lockfile_path.stat().st_size,
                    "modified": lockfile_path.stat().st_mtime
                }

        # Check for Node.js dependencies
        for lockfile in ["package-lock.json", "yarn.lock", "pnpm-lock.yaml"]:
            lockfile_path = Path(lockfile)
            if lockfile_path.exists():
                dependencies[lockfile] = {
                    "exists": True,
                    "checksum": self._calculate_file_checksum(lockfile_path),
                    "size": lockfile_path.stat().st_size,
                    "modified": lockfile_path.stat().st_mtime
                }

        return dependencies

    def _capture_test_baseline(self) -> Dict[str, Any]:
        """Capture test baseline information."""
        test_baseline = {}

        # Look for common test configuration files
        test_configs = [
            "pytest.ini", "pyproject.toml", "tox.ini", "setup.cfg",
            "jest.config.js", "package.json", ".eslintrc", "tsconfig.json"
        ]

        test_baseline["test_config_files"] = {}
        for config_file in test_configs:
            config_path = Path(config_file)
            if config_path.exists():
                test_baseline["test_config_files"][config_file] = {
                    "exists": True,
                    "checksum": self._calculate_file_checksum(config_path)
                }

        # Try to identify test directories
        test_dirs = []
        for potential_dir in ["tests", "test", "__tests__", "spec"]:
            test_path = Path(potential_dir)
            if test_path.exists() and test_path.is_dir():
                test_dirs.append(potential_dir)

        test_baseline["test_directories"] = test_dirs

        # Attempt to run tests and capture baseline (optional)
        test_baseline["baseline_run_attempted"] = False

        return test_baseline

    def _get_timestamp(self) -> str:
        """Get current timestamp in ISO format."""
        from datetime import datetime
        return datetime.utcnow().isoformat() + "Z"
