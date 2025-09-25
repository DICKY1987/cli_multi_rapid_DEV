#!/usr/bin/env python3
"""
Schema Validation Plugin for CLI Orchestrator

Validates JSON artifacts against JSON Schema definitions.
"""

import json
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


class SchemaValidatePlugin(BasePlugin):
    """Plugin for JSON Schema validation."""

    def __init__(self):
        super().__init__("schema_validate", "1.0.0")

    def get_capabilities(self) -> Dict[str, Any]:
        """Return plugin capabilities."""
        return {
            "description": "Validates JSON artifacts against JSON Schema definitions",
            "supported_formats": ["json"],
            "requires_tools": [],
            "outputs": ["schema_validation.json"],
            "gate_types": ["schema_valid"],
            "python_deps": ["jsonschema"],
        }

    def validate_config(self, config: Dict[str, Any]) -> bool:
        """Validate plugin configuration."""
        artifacts = config.get("artifacts", [])
        schema_dir = config.get("schema_dir", ".ai/schemas")

        if not isinstance(artifacts, list):
            console.print("[red]artifacts must be a list[/red]")
            return False

        if not isinstance(schema_dir, str):
            console.print("[red]schema_dir must be a string[/red]")
            return False

        return True

    def get_required_tools(self) -> list[str]:
        """Return required tools (none for this plugin)."""
        return []

    def execute(
        self, config: Dict[str, Any], artifacts_dir: Path, context: Dict[str, Any]
    ) -> PluginResult:
        """Execute schema validation."""

        # Configuration
        artifacts = config.get("artifacts", [])
        schema_dir = Path(config.get("schema_dir", ".ai/schemas"))
        schema_mapping = config.get("schema_mapping", {})

        # Ensure artifacts directory exists
        artifacts_dir.mkdir(parents=True, exist_ok=True)

        working_dir = context.get("working_dir", Path.cwd())
        full_schema_dir = working_dir / schema_dir

        validation_results = {
            "artifacts_validated": 0,
            "artifacts_passed": 0,
            "artifacts_failed": 0,
            "results": {},
            "errors": [],
        }

        # Check jsonschema availability
        try:
            import jsonschema
        except ImportError:
            return PluginResult(
                plugin_name=self.name,
                passed=False,
                message="jsonschema library not available",
                details={"error": "pip install jsonschema required"},
            )

        if not artifacts:
            return PluginResult(
                plugin_name=self.name,
                passed=True,
                message="No artifacts specified for validation",
                details=validation_results,
            )

        for artifact_path in artifacts:
            artifact_name = Path(artifact_path).name
            full_artifact_path = artifacts_dir / artifact_path

            validation_results["artifacts_validated"] += 1

            try:
                # Load artifact
                if not full_artifact_path.exists():
                    validation_results["errors"].append(
                        f"Artifact not found: {artifact_path}"
                    )
                    validation_results["results"][artifact_name] = {
                        "passed": False,
                        "error": "File not found",
                    }
                    validation_results["artifacts_failed"] += 1
                    continue

                with open(full_artifact_path, encoding="utf-8") as f:
                    artifact_data = json.load(f)

                # Determine schema file
                schema_file = None
                if artifact_path in schema_mapping:
                    schema_file = working_dir / schema_mapping[artifact_path]
                else:
                    # Use filename-based heuristics
                    schema_file = self._get_schema_for_artifact(
                        artifact_name, full_schema_dir
                    )

                if not schema_file or not schema_file.exists():
                    validation_results["results"][artifact_name] = {
                        "passed": True,  # Pass if no schema available
                        "message": "No schema found - skipped validation",
                        "schema_file": str(schema_file) if schema_file else None,
                    }
                    validation_results["artifacts_passed"] += 1
                    continue

                # Load schema
                with open(schema_file, encoding="utf-8") as f:
                    schema_data = json.load(f)

                # Validate
                jsonschema.validate(artifact_data, schema_data)

                validation_results["results"][artifact_name] = {
                    "passed": True,
                    "message": "Schema validation passed",
                    "schema_file": str(schema_file),
                }
                validation_results["artifacts_passed"] += 1

            except jsonschema.ValidationError as e:
                validation_results["results"][artifact_name] = {
                    "passed": False,
                    "error": f"Schema validation failed: {e.message}",
                    "schema_file": str(schema_file),
                }
                validation_results["artifacts_failed"] += 1

            except Exception as e:
                validation_results["results"][artifact_name] = {
                    "passed": False,
                    "error": f"Validation error: {str(e)}",
                }
                validation_results["artifacts_failed"] += 1

        # Write validation results
        with open(artifacts_dir / "schema_validation.json", "w", encoding="utf-8") as f:
            json.dump(validation_results, f, indent=2)

        # Determine overall success
        all_passed = validation_results["artifacts_failed"] == 0

        if all_passed:
            message = f"All {validation_results['artifacts_validated']} artifacts validated successfully"
        else:
            message = f"{validation_results['artifacts_failed']} of {validation_results['artifacts_validated']} artifacts failed validation"

        return PluginResult(
            plugin_name=self.name,
            passed=all_passed,
            message=message,
            details=validation_results,
            artifacts_created=["schema_validation.json"],
        )

    def _get_schema_for_artifact(self, artifact_name: str, schema_dir: Path) -> Path:
        """Determine schema file for an artifact using filename heuristics."""

        # Mapping based on artifact naming patterns
        schema_mappings = {
            "test_results.json": "test_results.schema.json",
            "coverage.json": "coverage.schema.json",
            "ruff_results.json": "ruff_results.schema.json",
            "semgrep_results.json": "semgrep_results.schema.json",
            "lint_summary.json": "lint_summary.schema.json",
            "ai-cost.json": "ai_cost.schema.json",
            "diagnostics.json": "diagnostics.schema.json",
        }

        # Direct mapping
        if artifact_name in schema_mappings:
            return schema_dir / schema_mappings[artifact_name]

        # Pattern-based matching
        if "code-review" in artifact_name:
            return schema_dir / "ai_code_review.schema.json"
        elif "architecture" in artifact_name:
            return schema_dir / "ai_architecture_analysis.schema.json"
        elif "refactor-plan" in artifact_name:
            return schema_dir / "ai_refactor_plan.schema.json"
        elif "test-plan" in artifact_name:
            return schema_dir / "ai_test_plan.schema.json"
        elif "improvements" in artifact_name:
            return schema_dir / "ai_improvements.schema.json"

        # Default: try artifact name + .schema.json
        return schema_dir / f"{Path(artifact_name).stem}.schema.json"
