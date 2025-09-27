#!/usr/bin/env python3
"""
Backup Manager Adapter

Creates recovery snapshots using git stash, file backups, and other mechanisms
to enable complete rollback if the modification pipeline fails.
"""

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any, Dict, Optional

from .base_adapter import AdapterResult, AdapterType, BaseAdapter


class BackupManagerAdapter(BaseAdapter):
    """Adapter for creating and managing recovery snapshots."""

    def __init__(self):
        super().__init__(
            name="backup_manager",
            adapter_type=AdapterType.DETERMINISTIC,
            description="Create recovery snapshots for rollback capability",
        )

    def execute(
        self,
        step: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None,
        files: Optional[str] = None,
    ) -> AdapterResult:
        """Execute backup creation."""
        self._log_execution_start(step)

        try:
            with_params = self._extract_with_params(step)
            snapshot_type = with_params.get("snapshot_type", "git_stash_plus_files")
            include_untracked = with_params.get("include_untracked", True)
            verify_backup = with_params.get("verify_backup", True)

            recovery_info = {
                "snapshot_timestamp": self._get_timestamp(),
                "snapshot_type": snapshot_type,
                "working_directory": str(Path.cwd()),
                "include_untracked": include_untracked,
                "verification_requested": verify_backup,
            }

            # Create backup based on type
            if snapshot_type == "git_stash_plus_files":
                backup_result = self._create_git_stash_backup(include_untracked)
            elif snapshot_type == "file_copy_backup":
                backup_result = self._create_file_copy_backup(include_untracked)
            elif snapshot_type == "git_commit_backup":
                backup_result = self._create_git_commit_backup(include_untracked)
            else:
                return AdapterResult(
                    success=False,
                    error=f"Unsupported snapshot type: {snapshot_type}"
                )

            recovery_info.update(backup_result)

            # Verify backup if requested
            if verify_backup:
                verification_result = self._verify_backup(recovery_info)
                recovery_info["verification"] = verification_result

                if not verification_result.get("verified", False):
                    return AdapterResult(
                        success=False,
                        error="Backup verification failed",
                        metadata=recovery_info
                    )

            # Write recovery information
            emit_paths = self._extract_emit_paths(step)
            artifacts = []

            if emit_paths:
                for emit_path in emit_paths:
                    artifact_path = Path(emit_path)
                    artifact_path.parent.mkdir(parents=True, exist_ok=True)

                    with open(artifact_path, 'w', encoding='utf-8') as f:
                        json.dump(recovery_info, f, indent=2)

                    artifacts.append(str(artifact_path))
                    self.logger.info(f"Recovery snapshot info written to: {artifact_path}")

            result = AdapterResult(
                success=True,
                tokens_used=0,  # Deterministic operation
                artifacts=artifacts,
                output=f"Created {snapshot_type} backup with verification: {verify_backup}",
                metadata=recovery_info
            )

            self._log_execution_complete(result)
            return result

        except Exception as e:
            error_msg = f"Backup creation failed: {str(e)}"
            self.logger.error(error_msg)
            return AdapterResult(
                success=False,
                error=error_msg,
                metadata={"exception_type": type(e).__name__}
            )

    def validate_step(self, step: Dict[str, Any]) -> bool:
        """Validate that this adapter can execute the given step."""
        # Basic validation - flexible parameters
        return True

    def estimate_cost(self, step: Dict[str, Any]) -> int:
        """Estimate token cost (0 for deterministic operations)."""
        return 0

    def is_available(self) -> bool:
        """Check if git is available for backup operations."""
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

    def _create_git_stash_backup(self, include_untracked: bool) -> Dict[str, Any]:
        """Create backup using git stash with optional untracked files."""
        backup_info = {"backup_method": "git_stash"}

        try:
            # Check if there are changes to stash
            result = subprocess.run(
                ["git", "status", "--porcelain"],
                capture_output=True,
                text=True,
                timeout=10
            )

            has_changes = len(result.stdout.strip()) > 0
            backup_info["had_changes_to_stash"] = has_changes

            if has_changes:
                # Create stash with message
                stash_message = f"CLI Orchestrator backup - {self._get_timestamp()}"

                if include_untracked:
                    stash_cmd = ["git", "stash", "push", "-u", "-m", stash_message]
                else:
                    stash_cmd = ["git", "stash", "push", "-m", stash_message]

                result = subprocess.run(
                    stash_cmd,
                    capture_output=True,
                    text=True,
                    timeout=30
                )

                if result.returncode != 0:
                    backup_info["error"] = f"Git stash failed: {result.stderr}"
                    return backup_info

                backup_info["stash_created"] = True
                backup_info["stash_message"] = stash_message

                # Get stash reference
                result = subprocess.run(
                    ["git", "stash", "list", "-1", "--format=%H"],
                    capture_output=True,
                    text=True,
                    timeout=10
                )

                if result.returncode == 0:
                    backup_info["stash_ref"] = result.stdout.strip()

            else:
                backup_info["stash_created"] = False
                backup_info["reason"] = "No changes to stash"

            # Also capture current commit as fallback
            result = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                capture_output=True,
                text=True,
                timeout=10
            )

            if result.returncode == 0:
                backup_info["fallback_commit"] = result.stdout.strip()

            backup_info["success"] = True

        except Exception as e:
            backup_info["success"] = False
            backup_info["error"] = str(e)

        return backup_info

    def _create_file_copy_backup(self, include_untracked: bool) -> Dict[str, Any]:
        """Create backup by copying files to a backup directory."""
        backup_info = {"backup_method": "file_copy"}

        try:
            # Create backup directory
            backup_dir = Path(".cli_orchestrator_backup")
            backup_dir.mkdir(exist_ok=True)

            # Clean existing backup
            if backup_dir.exists():
                shutil.rmtree(backup_dir)
            backup_dir.mkdir(parents=True, exist_ok=True)

            backup_info["backup_directory"] = str(backup_dir)

            # Get list of files to backup
            files_to_backup = []

            # Get tracked files
            result = subprocess.run(
                ["git", "ls-files"],
                capture_output=True,
                text=True,
                timeout=30
            )

            if result.returncode == 0:
                files_to_backup.extend(result.stdout.strip().split('\n'))

            # Get untracked files if requested
            if include_untracked:
                result = subprocess.run(
                    ["git", "ls-files", "--others", "--exclude-standard"],
                    capture_output=True,
                    text=True,
                    timeout=30
                )

                if result.returncode == 0:
                    untracked_files = result.stdout.strip().split('\n')
                    files_to_backup.extend([f for f in untracked_files if f.strip()])

            # Copy files
            copied_files = []
            for file_path in files_to_backup:
                if file_path.strip():
                    source_path = Path(file_path)
                    if source_path.exists() and source_path.is_file():
                        dest_path = backup_dir / file_path
                        dest_path.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(source_path, dest_path)
                        copied_files.append(file_path)

            backup_info["files_backed_up"] = len(copied_files)
            backup_info["success"] = True

        except Exception as e:
            backup_info["success"] = False
            backup_info["error"] = str(e)

        return backup_info

    def _create_git_commit_backup(self, include_untracked: bool) -> Dict[str, Any]:
        """Create backup by making a temporary commit."""
        backup_info = {"backup_method": "git_commit"}

        try:
            # Check if there are changes to commit
            result = subprocess.run(
                ["git", "status", "--porcelain"],
                capture_output=True,
                text=True,
                timeout=10
            )

            has_changes = len(result.stdout.strip()) > 0
            backup_info["had_changes_to_commit"] = has_changes

            if has_changes:
                # Add files to staging
                if include_untracked:
                    add_cmd = ["git", "add", "-A"]
                else:
                    add_cmd = ["git", "add", "-u"]

                result = subprocess.run(add_cmd, capture_output=True, text=True, timeout=30)
                if result.returncode != 0:
                    backup_info["error"] = f"Git add failed: {result.stderr}"
                    return backup_info

                # Create backup commit
                commit_message = f"[BACKUP] CLI Orchestrator backup - {self._get_timestamp()}"
                result = subprocess.run(
                    ["git", "commit", "-m", commit_message],
                    capture_output=True,
                    text=True,
                    timeout=30
                )

                if result.returncode != 0:
                    backup_info["error"] = f"Git commit failed: {result.stderr}"
                    return backup_info

                backup_info["backup_commit_created"] = True
                backup_info["commit_message"] = commit_message

                # Get commit hash
                result = subprocess.run(
                    ["git", "rev-parse", "HEAD"],
                    capture_output=True,
                    text=True,
                    timeout=10
                )

                if result.returncode == 0:
                    backup_info["backup_commit_hash"] = result.stdout.strip()

            else:
                backup_info["backup_commit_created"] = False
                backup_info["reason"] = "No changes to commit"

            backup_info["success"] = True

        except Exception as e:
            backup_info["success"] = False
            backup_info["error"] = str(e)

        return backup_info

    def _verify_backup(self, backup_info: Dict[str, Any]) -> Dict[str, Any]:
        """Verify that the backup was created successfully."""
        verification = {"verified": False, "checks": []}

        try:
            backup_method = backup_info.get("backup_method")

            if backup_method == "git_stash":
                # Verify stash exists
                if backup_info.get("stash_created"):
                    result = subprocess.run(
                        ["git", "stash", "list"],
                        capture_output=True,
                        text=True,
                        timeout=10
                    )
                    stash_exists = backup_info.get("stash_message", "") in result.stdout
                    verification["checks"].append({"stash_exists": stash_exists})
                    verification["verified"] = stash_exists
                else:
                    verification["verified"] = True  # No changes to stash is valid
                    verification["checks"].append({"no_changes_to_stash": True})

            elif backup_method == "file_copy":
                # Verify backup directory exists and has files
                backup_dir = Path(backup_info.get("backup_directory", ""))
                if backup_dir.exists():
                    file_count = len(list(backup_dir.rglob("*")))
                    verification["checks"].append({"backup_files_count": file_count})
                    verification["verified"] = file_count > 0
                else:
                    verification["checks"].append({"backup_directory_exists": False})

            elif backup_method == "git_commit":
                # Verify commit exists
                if backup_info.get("backup_commit_created"):
                    commit_hash = backup_info.get("backup_commit_hash")
                    if commit_hash:
                        result = subprocess.run(
                            ["git", "show", "--name-only", commit_hash],
                            capture_output=True,
                            text=True,
                            timeout=10
                        )
                        commit_exists = result.returncode == 0
                        verification["checks"].append({"backup_commit_exists": commit_exists})
                        verification["verified"] = commit_exists
                else:
                    verification["verified"] = True  # No changes to commit is valid
                    verification["checks"].append({"no_changes_to_commit": True})

        except Exception as e:
            verification["error"] = str(e)

        return verification

    def _get_timestamp(self) -> str:
        """Get current timestamp in ISO format."""
        from datetime import datetime
        return datetime.utcnow().isoformat() + "Z"
