#!/usr/bin/env python3
"""
Enhanced Bundle Applier Adapter

Applies modification bundles with atomic operations, dry-run capabilities,
and comprehensive verification. This is the core actor that performs the
actual code modifications in the Codex pipeline.
"""

import json
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Dict, Optional

from .base_adapter import AdapterResult, AdapterType, BaseAdapter


class EnhancedBundleApplierAdapter(BaseAdapter):
    """Adapter for applying modification bundles with enhanced safety."""

    def __init__(self):
        super().__init__(
            name="enhanced_bundle_applier",
            adapter_type=AdapterType.DETERMINISTIC,
            description="Apply modification bundles with atomic operations and verification",
        )

    def execute(
        self,
        step: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None,
        files: Optional[str] = None,
    ) -> AdapterResult:
        """Execute bundle application."""
        self._log_execution_start(step)

        try:
            with_params = self._extract_with_params(step)
            bundle_path = with_params.get("bundle_path")
            verification_mode = with_params.get("verification_mode", "standard")
            atomic_operations = with_params.get("atomic_operations", True)
            dry_run_first = with_params.get("dry_run_first", True)

            if not bundle_path:
                return AdapterResult(
                    success=False,
                    error="Missing required parameter: bundle_path"
                )

            # Load bundle
            bundle_data = self._load_bundle(bundle_path)
            if not bundle_data:
                return AdapterResult(
                    success=False,
                    error=f"Failed to load bundle from: {bundle_path}"
                )

            application_result = {
                "bundle_path": bundle_path,
                "verification_mode": verification_mode,
                "atomic_operations": atomic_operations,
                "dry_run_first": dry_run_first,
                "applied_at": self._get_timestamp(),
            }

            # Perform dry run if requested
            if dry_run_first:
                dry_run_result = self._perform_dry_run(bundle_data)
                application_result["dry_run"] = dry_run_result

                if not dry_run_result.get("success", False):
                    return AdapterResult(
                        success=False,
                        error=f"Dry run failed: {dry_run_result.get('error', 'Unknown error')}",
                        metadata=application_result
                    )

            # Apply modifications
            if atomic_operations:
                apply_result = self._apply_atomic_modifications(bundle_data, verification_mode)
            else:
                apply_result = self._apply_sequential_modifications(bundle_data, verification_mode)

            application_result["application"] = apply_result

            if not apply_result.get("success", False):
                return AdapterResult(
                    success=False,
                    error=f"Bundle application failed: {apply_result.get('error', 'Unknown error')}",
                    metadata=application_result
                )

            # Write application result
            emit_paths = self._extract_emit_paths(step)
            artifacts = []

            if emit_paths:
                for emit_path in emit_paths:
                    artifact_path = Path(emit_path)
                    artifact_path.parent.mkdir(parents=True, exist_ok=True)

                    with open(artifact_path, 'w', encoding='utf-8') as f:
                        json.dump(application_result, f, indent=2)

                    artifacts.append(str(artifact_path))
                    self.logger.info(f"Application result written to: {artifact_path}")

            result = AdapterResult(
                success=True,
                tokens_used=0,  # Deterministic operation
                artifacts=artifacts,
                output=f"Successfully applied {len(bundle_data.get('patches', []))} patches",
                metadata=application_result
            )

            self._log_execution_complete(result)
            return result

        except Exception as e:
            error_msg = f"Bundle application failed: {str(e)}"
            self.logger.error(error_msg)
            return AdapterResult(
                success=False,
                error=error_msg,
                metadata={"exception_type": type(e).__name__}
            )

    def validate_step(self, step: Dict[str, Any]) -> bool:
        """Validate that this adapter can execute the given step."""
        with_params = self._extract_with_params(step)
        return "bundle_path" in with_params

    def estimate_cost(self, step: Dict[str, Any]) -> int:
        """Estimate token cost (0 for deterministic operations)."""
        return 0

    def is_available(self) -> bool:
        """Check if git and other tools are available."""
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

    def _load_bundle(self, bundle_path: str) -> Optional[Dict[str, Any]]:
        """Load bundle from file."""
        try:
            with open(bundle_path, encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            self.logger.error(f"Failed to load bundle {bundle_path}: {e}")
            return None

    def _perform_dry_run(self, bundle_data: Dict[str, Any]) -> Dict[str, Any]:
        """Perform a dry run of the bundle application."""
        dry_run_result = {
            "success": True,
            "patches_analyzed": 0,
            "target_files": [],
            "issues": [],
            "warnings": []
        }

        try:
            patches = bundle_data.get("patches", [])

            for i, patch in enumerate(patches):
                patch_analysis = self._analyze_patch_dry_run(patch, i)

                if not patch_analysis["can_apply"]:
                    dry_run_result["issues"].append({
                        "patch_index": i,
                        "issue": patch_analysis["issue"],
                        "target_path": patch_analysis.get("target_path")
                    })
                    dry_run_result["success"] = False

                if patch_analysis.get("warnings"):
                    dry_run_result["warnings"].extend(patch_analysis["warnings"])

                target_path = patch_analysis.get("target_path")
                if target_path and target_path not in dry_run_result["target_files"]:
                    dry_run_result["target_files"].append(target_path)

                dry_run_result["patches_analyzed"] += 1

            dry_run_result["total_patches"] = len(patches)
            dry_run_result["total_target_files"] = len(dry_run_result["target_files"])

        except Exception as e:
            dry_run_result["success"] = False
            dry_run_result["error"] = str(e)

        return dry_run_result

    def _analyze_patch_dry_run(self, patch: Dict[str, Any], index: int) -> Dict[str, Any]:
        """Analyze a single patch for dry run."""
        analysis = {
            "can_apply": True,
            "warnings": [],
            "patch_index": index
        }

        try:
            # Get target file
            target = patch.get("target", {})
            target_path = target.get("path")
            analysis["target_path"] = target_path

            if not target_path:
                analysis["can_apply"] = False
                analysis["issue"] = "No target path specified"
                return analysis

            # Check if target file exists
            target_file = Path(target_path)
            if not target_file.exists():
                analysis["can_apply"] = False
                analysis["issue"] = f"Target file does not exist: {target_path}"
                return analysis

            # Check file permissions
            if not target_file.is_file():
                analysis["can_apply"] = False
                analysis["issue"] = f"Target is not a regular file: {target_path}"
                return analysis

            # Check if file is writable
            if not os.access(target_file, os.W_OK):
                analysis["warnings"].append(f"Target file may not be writable: {target_path}")

            # Validate patch operations
            ops = patch.get("ops", [])
            if not ops:
                analysis["warnings"].append(f"Patch {index} has no operations")

            # Check pre-conditions if specified
            if "pre" in patch:
                pre_check = self._check_pre_conditions(patch["pre"], target_file)
                if not pre_check["passed"]:
                    analysis["can_apply"] = False
                    analysis["issue"] = f"Pre-condition failed: {pre_check['error']}"

        except Exception as e:
            analysis["can_apply"] = False
            analysis["issue"] = f"Analysis failed: {str(e)}"

        return analysis

    def _apply_atomic_modifications(self, bundle_data: Dict[str, Any], verification_mode: str) -> Dict[str, Any]:
        """Apply all modifications atomically using temporary files."""
        apply_result = {
            "success": True,
            "method": "atomic",
            "patches_applied": 0,
            "files_modified": [],
            "rollback_info": []
        }

        # Create temporary backup of all target files
        temp_backup_map = {}
        patches = bundle_data.get("patches", [])

        try:
            # Create backups of all target files
            for patch in patches:
                target_path = patch.get("target", {}).get("path")
                if target_path and target_path not in temp_backup_map:
                    original_file = Path(target_path)
                    if original_file.exists():
                        # Create temporary backup
                        backup_fd, backup_path = tempfile.mkstemp(suffix=f"_{original_file.name}.backup")
                        with os.fdopen(backup_fd, 'wb') as backup_f:
                            with open(original_file, 'rb') as orig_f:
                                shutil.copyfileobj(orig_f, backup_f)

                        temp_backup_map[target_path] = backup_path
                        apply_result["rollback_info"].append({
                            "original": target_path,
                            "backup": backup_path
                        })

            # Apply all patches
            for i, patch in enumerate(patches):
                patch_result = self._apply_single_patch(patch, i, verification_mode)

                if not patch_result["success"]:
                    # Rollback all changes
                    self._rollback_from_backups(temp_backup_map)
                    apply_result["success"] = False
                    apply_result["error"] = f"Patch {i} failed: {patch_result['error']}"
                    apply_result["failed_patch_index"] = i
                    return apply_result

                apply_result["patches_applied"] += 1
                target_path = patch.get("target", {}).get("path")
                if target_path and target_path not in apply_result["files_modified"]:
                    apply_result["files_modified"].append(target_path)

            # Clean up backup files on success
            for backup_path in temp_backup_map.values():
                try:
                    os.unlink(backup_path)
                except OSError:
                    pass  # Backup cleanup is not critical

            apply_result["total_patches"] = len(patches)
            apply_result["total_files_modified"] = len(apply_result["files_modified"])

        except Exception as e:
            # Rollback on any exception
            self._rollback_from_backups(temp_backup_map)
            apply_result["success"] = False
            apply_result["error"] = str(e)

        return apply_result

    def _apply_sequential_modifications(self, bundle_data: Dict[str, Any], verification_mode: str) -> Dict[str, Any]:
        """Apply modifications sequentially (less safe but simpler)."""
        apply_result = {
            "success": True,
            "method": "sequential",
            "patches_applied": 0,
            "files_modified": []
        }

        try:
            patches = bundle_data.get("patches", [])

            for i, patch in enumerate(patches):
                patch_result = self._apply_single_patch(patch, i, verification_mode)

                if not patch_result["success"]:
                    apply_result["success"] = False
                    apply_result["error"] = f"Patch {i} failed: {patch_result['error']}"
                    apply_result["failed_patch_index"] = i
                    return apply_result

                apply_result["patches_applied"] += 1
                target_path = patch.get("target", {}).get("path")
                if target_path and target_path not in apply_result["files_modified"]:
                    apply_result["files_modified"].append(target_path)

            apply_result["total_patches"] = len(patches)
            apply_result["total_files_modified"] = len(apply_result["files_modified"])

        except Exception as e:
            apply_result["success"] = False
            apply_result["error"] = str(e)

        return apply_result

    def _apply_single_patch(self, patch: Dict[str, Any], index: int, verification_mode: str) -> Dict[str, Any]:
        """Apply a single patch to its target file."""
        patch_result = {"success": True}

        try:
            target_path = patch.get("target", {}).get("path")
            patch_type = patch.get("type", "unified_diff")

            if patch_type == "unified_diff":
                return self._apply_unified_diff_patch(patch, index)
            else:
                return {
                    "success": False,
                    "error": f"Unsupported patch type: {patch_type}"
                }

        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }

    def _apply_unified_diff_patch(self, patch: Dict[str, Any], index: int) -> Dict[str, Any]:
        """Apply a unified diff patch."""
        try:
            target_path = patch.get("target", {}).get("path")
            ops = patch.get("ops", [])

            if not ops:
                return {"success": True, "message": "No operations to apply"}

            target_file = Path(target_path)

            # For now, we'll implement a basic diff application
            # In a production system, you'd want a more robust diff parser
            for op in ops:
                if "diff" in op:
                    # Apply the diff using git apply or patch command
                    diff_content = op["diff"]
                    result = self._apply_diff_content(diff_content, target_file)
                    if not result["success"]:
                        return result

            return {"success": True, "operations_applied": len(ops)}

        except Exception as e:
            return {"success": False, "error": str(e)}

    def _apply_diff_content(self, diff_content: str, target_file: Path) -> Dict[str, Any]:
        """Apply diff content to a target file."""
        try:
            # Write diff to temporary file
            with tempfile.NamedTemporaryFile(mode='w', suffix='.patch', delete=False) as patch_file:
                patch_file.write(diff_content)
                patch_file_path = patch_file.name

            # Apply patch using git apply
            result = subprocess.run(
                ["git", "apply", "--check", patch_file_path],
                capture_output=True,
                text=True,
                timeout=30,
                cwd=target_file.parent
            )

            if result.returncode != 0:
                os.unlink(patch_file_path)
                return {
                    "success": False,
                    "error": f"Patch check failed: {result.stderr}"
                }

            # Apply the patch
            result = subprocess.run(
                ["git", "apply", patch_file_path],
                capture_output=True,
                text=True,
                timeout=30,
                cwd=target_file.parent
            )

            os.unlink(patch_file_path)

            if result.returncode == 0:
                return {"success": True}
            else:
                return {
                    "success": False,
                    "error": f"Patch apply failed: {result.stderr}"
                }

        except Exception as e:
            return {"success": False, "error": str(e)}

    def _check_pre_conditions(self, pre_conditions: Dict[str, Any], target_file: Path) -> Dict[str, Any]:
        """Check pre-conditions for a patch."""
        result = {"passed": True}

        try:
            # Check hash if specified
            if "hash" in pre_conditions:
                expected_hash = pre_conditions["hash"].get("sha256")
                if expected_hash:
                    actual_hash = self._calculate_file_hash(target_file)
                    if actual_hash != expected_hash:
                        result["passed"] = False
                        result["error"] = f"File hash mismatch. Expected: {expected_hash}, Actual: {actual_hash}"

        except Exception as e:
            result["passed"] = False
            result["error"] = str(e)

        return result

    def _calculate_file_hash(self, file_path: Path) -> str:
        """Calculate SHA256 hash of a file."""
        import hashlib
        sha256_hash = hashlib.sha256()
        with open(file_path, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()

    def _rollback_from_backups(self, backup_map: Dict[str, str]) -> None:
        """Rollback files from their temporary backups."""
        for original_path, backup_path in backup_map.items():
            try:
                if os.path.exists(backup_path):
                    shutil.copy2(backup_path, original_path)
                    os.unlink(backup_path)
                    self.logger.info(f"Rolled back: {original_path}")
            except Exception as e:
                self.logger.error(f"Failed to rollback {original_path}: {e}")

    def _get_timestamp(self) -> str:
        """Get current timestamp in ISO format."""
        from datetime import datetime
        return datetime.utcnow().isoformat() + "Z"


# Import os for file operations
import os
