#!/usr/bin/env python3
"""
Contract Validator Adapter

Validates modification contracts against JSON Schema to ensure they meet
all requirements for the Codex 100% Accurate Modification Pipeline.
"""

import json
from pathlib import Path
from typing import Any, Dict, Optional

import jsonschema
import yaml
from jsonschema import validate

from .base_adapter import AdapterResult, AdapterType, BaseAdapter


class ContractValidatorAdapter(BaseAdapter):
    """Adapter for validating modification contracts against schemas."""

    def __init__(self):
        super().__init__(
            name="contract_validator",
            adapter_type=AdapterType.DETERMINISTIC,
            description="Validate modification contracts against JSON schemas",
        )

    def execute(
        self,
        step: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None,
        files: Optional[str] = None,
    ) -> AdapterResult:
        """Execute contract validation."""
        self._log_execution_start(step)

        try:
            with_params = self._extract_with_params(step)
            contract_file = with_params.get("contract_file")
            schema_path = with_params.get("schema_path")
            strict_validation = with_params.get("strict_validation", True)

            if not contract_file:
                return AdapterResult(
                    success=False,
                    error="Missing required parameter: contract_file"
                )

            if not schema_path:
                return AdapterResult(
                    success=False,
                    error="Missing required parameter: schema_path"
                )

            # Load contract file
            contract_path = Path(contract_file)
            if not contract_path.exists():
                return AdapterResult(
                    success=False,
                    error=f"Contract file not found: {contract_file}"
                )

            # Load contract content
            with open(contract_path, encoding='utf-8') as f:
                if contract_path.suffix.lower() in ['.yaml', '.yml']:
                    contract_data = yaml.safe_load(f)
                else:
                    contract_data = json.load(f)

            # Load schema
            schema_path_obj = Path(schema_path)
            if not schema_path_obj.exists():
                return AdapterResult(
                    success=False,
                    error=f"Schema file not found: {schema_path}"
                )

            with open(schema_path_obj, encoding='utf-8') as f:
                schema = json.load(f)

            # Validate contract against schema
            try:
                validate(instance=contract_data, schema=schema)
            except jsonschema.ValidationError as e:
                error_msg = f"Contract validation failed: {e.message}"
                if strict_validation:
                    return AdapterResult(
                        success=False,
                        error=error_msg,
                        metadata={"validation_error": str(e)}
                    )
                else:
                    self.logger.warning(f"Non-strict mode: {error_msg}")

            # Generate validation report
            validation_result = {
                "contract_file": str(contract_file),
                "schema_path": str(schema_path),
                "validation_status": "passed",
                "strict_mode": strict_validation,
                "contract_version": contract_data.get("contract_version", "unknown"),
                "modification_id": contract_data.get("modification_id", "unknown"),
                "validated_at": self._get_timestamp(),
            }

            # Write validation artifact
            emit_paths = self._extract_emit_paths(step)
            artifacts = []

            if emit_paths:
                for emit_path in emit_paths:
                    artifact_path = Path(emit_path)
                    artifact_path.parent.mkdir(parents=True, exist_ok=True)

                    with open(artifact_path, 'w', encoding='utf-8') as f:
                        json.dump(validation_result, f, indent=2)

                    artifacts.append(str(artifact_path))
                    self.logger.info(f"Validation result written to: {artifact_path}")

            result = AdapterResult(
                success=True,
                tokens_used=0,  # Deterministic operation
                artifacts=artifacts,
                output=f"Contract validation passed for {contract_file}",
                metadata=validation_result
            )

            self._log_execution_complete(result)
            return result

        except Exception as e:
            error_msg = f"Contract validation failed with error: {str(e)}"
            self.logger.error(error_msg)
            return AdapterResult(
                success=False,
                error=error_msg,
                metadata={"exception_type": type(e).__name__}
            )

    def validate_step(self, step: Dict[str, Any]) -> bool:
        """Validate that this adapter can execute the given step."""
        with_params = self._extract_with_params(step)
        return "contract_file" in with_params and "schema_path" in with_params

    def estimate_cost(self, step: Dict[str, Any]) -> int:
        """Estimate token cost (0 for deterministic operations)."""
        return 0

    def is_available(self) -> bool:
        """Check if required dependencies are available."""
        try:
            import jsonschema
            import yaml
            return True
        except ImportError:
            return False

    def _get_timestamp(self) -> str:
        """Get current timestamp in ISO format."""
        from datetime import datetime
        return datetime.utcnow().isoformat() + "Z"
