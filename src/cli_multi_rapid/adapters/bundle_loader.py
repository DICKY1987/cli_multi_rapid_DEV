#!/usr/bin/env python3
"""
Bundle Loader Adapter

Loads and validates edit contract bundles for the Codex modification pipeline.
Ensures bundles meet schema requirements and pre-validates modifications.
"""

import json
from pathlib import Path
from typing import Any, Dict, Optional

import jsonschema
from jsonschema import validate

from .base_adapter import AdapterResult, AdapterType, BaseAdapter


class BundleLoaderAdapter(BaseAdapter):
    """Adapter for loading and validating edit contract bundles."""

    def __init__(self):
        super().__init__(
            name="bundle_loader",
            adapter_type=AdapterType.DETERMINISTIC,
            description="Load and validate edit contract bundles",
        )

    def execute(
        self,
        step: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None,
        files: Optional[str] = None,
    ) -> AdapterResult:
        """Execute bundle loading and validation."""
        self._log_execution_start(step)

        try:
            with_params = self._extract_with_params(step)
            bundle_path = with_params.get("bundle_path")
            validation_schema = with_params.get("validation_schema")
            pre_validation = with_params.get("pre_validation", True)

            if not bundle_path:
                return AdapterResult(
                    success=False,
                    error="Missing required parameter: bundle_path"
                )

            if not validation_schema:
                return AdapterResult(
                    success=False,
                    error="Missing required parameter: validation_schema"
                )

            # Load bundle file
            bundle_file = Path(bundle_path)
            if not bundle_file.exists():
                return AdapterResult(
                    success=False,
                    error=f"Bundle file not found: {bundle_path}"
                )

            with open(bundle_file, encoding='utf-8') as f:
                bundle_data = json.load(f)

            # Load validation schema
            schema_file = Path(validation_schema)
            if not schema_file.exists():
                return AdapterResult(
                    success=False,
                    error=f"Schema file not found: {validation_schema}"
                )

            with open(schema_file, encoding='utf-8') as f:
                schema = json.load(f)

            # Validate bundle against schema
            try:
                validate(instance=bundle_data, schema=schema)
                schema_validation_passed = True
                schema_validation_error = None
            except jsonschema.ValidationError as e:
                schema_validation_passed = False
                schema_validation_error = str(e)

            if not schema_validation_passed:
                return AdapterResult(
                    success=False,
                    error=f"Bundle schema validation failed: {schema_validation_error}",
                    metadata={
                        "bundle_path": bundle_path,
                        "validation_schema": validation_schema,
                        "schema_validation_error": schema_validation_error
                    }
                )

            # Pre-validate bundle contents
            pre_validation_results = {}
            if pre_validation:
                pre_validation_results = self._pre_validate_bundle(bundle_data)

                if not pre_validation_results.get("valid", True):
                    return AdapterResult(
                        success=False,
                        error=f"Bundle pre-validation failed: {pre_validation_results.get('error', 'Unknown error')}",
                        metadata={
                            "bundle_path": bundle_path,
                            "pre_validation_results": pre_validation_results
                        }
                    )

            # Create loaded bundle result
            loaded_bundle = {
                "bundle_path": bundle_path,
                "validation_schema": validation_schema,
                "loaded_at": self._get_timestamp(),
                "schema_validation": {
                    "passed": schema_validation_passed,
                    "error": schema_validation_error
                },
                "pre_validation": pre_validation_results,
                "bundle_metadata": {
                    "version": bundle_data.get("version", "unknown"),
                    "contract_id": bundle_data.get("contract_id", "unknown"),
                    "generated_by": bundle_data.get("generated_by", "unknown"),
                    "validation_level": bundle_data.get("validation_level", "unknown"),
                    "patch_count": len(bundle_data.get("patches", [])),
                    "verification_gate_count": len(bundle_data.get("verification_gates", []))
                },
                "bundle_content": bundle_data
            }

            # Write loaded bundle artifact
            emit_paths = self._extract_emit_paths(step)
            artifacts = []

            if emit_paths:
                for emit_path in emit_paths:
                    artifact_path = Path(emit_path)
                    artifact_path.parent.mkdir(parents=True, exist_ok=True)

                    with open(artifact_path, 'w', encoding='utf-8') as f:
                        json.dump(loaded_bundle, f, indent=2)

                    artifacts.append(str(artifact_path))
                    self.logger.info(f"Loaded bundle written to: {artifact_path}")

            result = AdapterResult(
                success=True,
                tokens_used=0,  # Deterministic operation
                artifacts=artifacts,
                output=f"Successfully loaded and validated bundle: {bundle_path}",
                metadata=loaded_bundle
            )

            self._log_execution_complete(result)
            return result

        except Exception as e:
            error_msg = f"Bundle loading failed: {str(e)}"
            self.logger.error(error_msg)
            return AdapterResult(
                success=False,
                error=error_msg,
                metadata={"exception_type": type(e).__name__}
            )

    def validate_step(self, step: Dict[str, Any]) -> bool:
        """Validate that this adapter can execute the given step."""
        with_params = self._extract_with_params(step)
        return "bundle_path" in with_params and "validation_schema" in with_params

    def estimate_cost(self, step: Dict[str, Any]) -> int:
        """Estimate token cost (0 for deterministic operations)."""
        return 0

    def is_available(self) -> bool:
        """Check if required dependencies are available."""
        try:
            import jsonschema
            return True
        except ImportError:
            return False

    def _pre_validate_bundle(self, bundle_data: Dict[str, Any]) -> Dict[str, Any]:
        """Perform pre-validation checks on bundle contents."""
        validation_result = {
            "valid": True,
            "checks": [],
            "warnings": [],
            "errors": []
        }

        try:
            # Check required fields
            required_fields = ["version", "contract_id", "patches"]
            for field in required_fields:
                if field not in bundle_data:
                    validation_result["errors"].append(f"Missing required field: {field}")
                    validation_result["valid"] = False
                else:
                    validation_result["checks"].append(f"Required field '{field}' present")

            # Validate patches structure
            patches = bundle_data.get("patches", [])
            if not isinstance(patches, list):
                validation_result["errors"].append("'patches' must be a list")
                validation_result["valid"] = False
            else:
                validation_result["checks"].append(f"Found {len(patches)} patches")

                # Validate each patch
                for i, patch in enumerate(patches):
                    patch_validation = self._validate_patch(patch, i)
                    if not patch_validation["valid"]:
                        validation_result["errors"].extend(patch_validation["errors"])
                        validation_result["valid"] = False
                    validation_result["checks"].extend(patch_validation["checks"])

            # Validate verification gates
            gates = bundle_data.get("verification_gates", [])
            if gates and not isinstance(gates, list):
                validation_result["errors"].append("'verification_gates' must be a list")
                validation_result["valid"] = False
            else:
                validation_result["checks"].append(f"Found {len(gates)} verification gates")

            # Check for potential conflicts
            target_files = []
            for patch in patches:
                if isinstance(patch, dict) and "target" in patch:
                    target_path = patch["target"].get("path")
                    if target_path:
                        if target_path in target_files:
                            validation_result["warnings"].append(f"Multiple patches target same file: {target_path}")
                        target_files.append(target_path)

            validation_result["target_files"] = target_files

        except Exception as e:
            validation_result["valid"] = False
            validation_result["errors"].append(f"Pre-validation exception: {str(e)}")

        return validation_result

    def _validate_patch(self, patch: Any, index: int) -> Dict[str, Any]:
        """Validate an individual patch structure."""
        patch_validation = {
            "valid": True,
            "checks": [],
            "errors": []
        }

        if not isinstance(patch, dict):
            patch_validation["errors"].append(f"Patch {index} is not a dictionary")
            patch_validation["valid"] = False
            return patch_validation

        # Check required patch fields
        required_patch_fields = ["type", "target", "ops"]
        for field in required_patch_fields:
            if field not in patch:
                patch_validation["errors"].append(f"Patch {index} missing required field: {field}")
                patch_validation["valid"] = False
            else:
                patch_validation["checks"].append(f"Patch {index} has required field '{field}'")

        # Validate target structure
        if "target" in patch:
            target = patch["target"]
            if not isinstance(target, dict) or "path" not in target:
                patch_validation["errors"].append(f"Patch {index} target must be a dict with 'path' field")
                patch_validation["valid"] = False

        # Validate operations structure
        if "ops" in patch:
            ops = patch["ops"]
            if not isinstance(ops, list):
                patch_validation["errors"].append(f"Patch {index} ops must be a list")
                patch_validation["valid"] = False
            else:
                patch_validation["checks"].append(f"Patch {index} has {len(ops)} operations")

        # Check for pre/post assertions
        if "pre" in patch:
            patch_validation["checks"].append(f"Patch {index} has pre-assertions")
        if "post" in patch:
            patch_validation["checks"].append(f"Patch {index} has post-assertions")

        return patch_validation

    def _get_timestamp(self) -> str:
        """Get current timestamp in ISO format."""
        from datetime import datetime
        return datetime.utcnow().isoformat() + "Z"
