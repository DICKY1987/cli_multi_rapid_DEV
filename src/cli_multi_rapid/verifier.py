#!/usr/bin/env python3
"""
CLI Orchestrator Verifier

Implements gate-based quality control system for validating artifacts,
checking test results, and enforcing quality standards.
"""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

from rich.console import Console

console = Console()


@dataclass
class GateResult:
    """Result of a quality gate check."""

    gate_name: str
    passed: bool
    message: str
    details: dict[str, Any] = None

    def __post_init__(self):
        if self.details is None:
            self.details = {}


class Verifier:
    """Validates artifacts and enforces quality gates."""

    def __init__(self):
        self.console = Console()

    def verify_artifact(
        self, artifact_file: Path, schema_file: Optional[Path] = None
    ) -> bool:
        """Verify an artifact against its JSON schema."""

        try:
            if not artifact_file.exists():
                console.print(f"[red]Artifact file not found: {artifact_file}[/red]")
                return False

            # Load artifact
            with open(artifact_file, encoding="utf-8") as f:
                artifact = json.load(f)

            console.print(f"[blue]Loaded artifact: {artifact_file.name}[/blue]")

            # Schema validation
            if schema_file and schema_file.exists():
                return self._validate_against_schema(artifact, schema_file)
            else:
                console.print(
                    "[yellow]No schema file specified - basic validation only[/yellow]"
                )
                return self._basic_validation(artifact)

        except Exception as e:
            console.print(f"[red]Artifact verification error: {e}[/red]")
            return False

    def _validate_against_schema(
        self, artifact: dict[str, Any], schema_file: Path
    ) -> bool:
        """Validate artifact against JSON schema."""
        try:
            import jsonschema

            with open(schema_file, encoding="utf-8") as f:
                schema = json.load(f)

            jsonschema.validate(artifact, schema)
            console.print("[green]✓ Schema validation passed[/green]")
            return True

        except ImportError:
            console.print(
                "[yellow]jsonschema not available - skipping schema validation[/yellow]"
            )
            return self._basic_validation(artifact)
        except Exception as e:
            console.print(f"[red]Schema validation failed: {e}[/red]")
            return False

    def _basic_validation(self, artifact: dict[str, Any]) -> bool:
        """Perform basic validation checks."""
        # Check for required top-level fields
        required_fields = ["timestamp", "type"]
        missing_fields = [field for field in required_fields if field not in artifact]

        if missing_fields:
            console.print(f"[red]Missing required fields: {missing_fields}[/red]")
            return False

        console.print("[green]✓ Basic validation passed[/green]")
        return True

    def check_gates(
        self, gates: list[dict[str, Any]], artifacts_dir: Path = Path("artifacts")
    ) -> list[GateResult]:
        """Check multiple quality gates."""

        results = []

        for gate_config in gates:
            gate_type = gate_config.get("type", "unknown")
            gate_name = gate_config.get("name", gate_type)

            console.print(f"[cyan]Checking gate: {gate_name}[/cyan]")

            result = self._check_single_gate(gate_config, artifacts_dir)
            results.append(result)

            if result.passed:
                console.print(f"[green]✓ {gate_name}: {result.message}[/green]")
            else:
                console.print(f"[red]✗ {gate_name}: {result.message}[/red]")

        return results

    def _check_single_gate(
        self, gate_config: dict[str, Any], artifacts_dir: Path
    ) -> GateResult:
        """Check a single quality gate."""

        gate_type = gate_config.get("type", "unknown")
        gate_name = gate_config.get("name", gate_type)

        try:
            if gate_type == "tests_pass":
                return self._check_tests_pass_gate(gate_config, artifacts_dir)
            elif gate_type == "diff_limits":
                return self._check_diff_limits_gate(gate_config, artifacts_dir)
            elif gate_type == "schema_valid":
                return self._check_schema_valid_gate(gate_config, artifacts_dir)
            elif gate_type == "token_budget":
                return self._check_token_budget_gate(gate_config, artifacts_dir)
            else:
                return GateResult(
                    gate_name=gate_name,
                    passed=False,
                    message=f"Unknown gate type: {gate_type}",
                )

        except Exception as e:
            return GateResult(
                gate_name=gate_name, passed=False, message=f"Gate check error: {str(e)}"
            )

    def _check_tests_pass_gate(
        self, gate_config: dict[str, Any], artifacts_dir: Path
    ) -> GateResult:
        """Check if test results indicate passing tests."""

        test_report_file = artifacts_dir / gate_config.get(
            "test_report", "test_results.json"
        )

        if not test_report_file.exists():
            return GateResult(
                gate_name="tests_pass",
                passed=False,
                message=f"Test report not found: {test_report_file}",
            )

        try:
            with open(test_report_file, encoding="utf-8") as f:
                test_report = json.load(f)

            tests_passed = test_report.get("tests_passed", 0)
            tests_failed = test_report.get("tests_failed", 0)
            total_tests = tests_passed + tests_failed

            if tests_failed > 0:
                return GateResult(
                    gate_name="tests_pass",
                    passed=False,
                    message=f"{tests_failed} tests failed out of {total_tests}",
                    details={
                        "tests_passed": tests_passed,
                        "tests_failed": tests_failed,
                        "total_tests": total_tests,
                    },
                )

            return GateResult(
                gate_name="tests_pass",
                passed=True,
                message=f"All {tests_passed} tests passed",
                details={"tests_passed": tests_passed, "total_tests": total_tests},
            )

        except Exception as e:
            return GateResult(
                gate_name="tests_pass",
                passed=False,
                message=f"Could not read test report: {e}",
            )

    def _check_diff_limits_gate(
        self, gate_config: dict[str, Any], artifacts_dir: Path
    ) -> GateResult:
        """Check if diff size is within acceptable limits."""

        max_lines = gate_config.get("max_lines", 1000)
        diff_file = artifacts_dir / gate_config.get("diff_file", "changes.diff")

        if not diff_file.exists():
            # No diff file might mean no changes, which could be acceptable
            return GateResult(
                gate_name="diff_limits",
                passed=True,
                message="No diff file found - assuming no changes",
            )

        try:
            with open(diff_file, encoding="utf-8") as f:
                lines = f.readlines()

            line_count = len(lines)

            if line_count > max_lines:
                return GateResult(
                    gate_name="diff_limits",
                    passed=False,
                    message=f"Diff too large: {line_count} lines (max: {max_lines})",
                    details={"line_count": line_count, "max_lines": max_lines},
                )

            return GateResult(
                gate_name="diff_limits",
                passed=True,
                message=f"Diff size acceptable: {line_count} lines",
                details={"line_count": line_count, "max_lines": max_lines},
            )

        except Exception as e:
            return GateResult(
                gate_name="diff_limits",
                passed=False,
                message=f"Could not read diff file: {e}",
            )

    def _check_schema_valid_gate(
        self, gate_config: dict[str, Any], artifacts_dir: Path
    ) -> GateResult:
        """Check if all artifacts have valid schemas.

        Expects a list of artifact paths under gate_config['artifacts'] and
        uses a filename→schema heuristic unless an explicit mapping is given.
        """

        try:
            artifacts = gate_config.get("artifacts", [])
            schema_dir = Path(gate_config.get("schema_dir", ".ai/schemas"))
            mapping: dict[str, str] = gate_config.get("schema_map", {})

            if not artifacts:
                return GateResult(
                    gate_name="schema_valid",
                    passed=True,
                    message="No artifacts specified",
                )

            all_ok = True
            details: dict[str, Any] = {}
            for art in artifacts:
                art_path = artifacts_dir / art if not art.startswith("/") else Path(art)
                # Determine schema path
                schema_file: Optional[Path] = None
                if mapping and art in mapping:
                    schema_file = Path(mapping[art])
                else:
                    name = Path(art).name
                    if "code-review" in name:
                        schema_file = schema_dir / "ai_code_review.schema.json"
                    elif "architecture" in name:
                        schema_file = (
                            schema_dir / "ai_architecture_analysis.schema.json"
                        )
                    elif "refactor-plan" in name:
                        schema_file = schema_dir / "ai_refactor_plan.schema.json"
                    elif "test-plan" in name:
                        schema_file = schema_dir / "ai_test_plan.schema.json"
                    elif "improvements" in name:
                        schema_file = schema_dir / "ai_improvements.schema.json"

                ok = self.verify_artifact(art_path, schema_file)
                details[str(art_path)] = ok
                all_ok = all_ok and ok

            return GateResult(
                gate_name="schema_valid",
                passed=all_ok,
                message=(
                    "All artifacts valid" if all_ok else "One or more artifacts invalid"
                ),
                details=details,
            )
        except Exception as e:
            return GateResult(
                gate_name="schema_valid",
                passed=False,
                message=f"Schema gate error: {e}",
            )

    def _check_token_budget_gate(
        self, gate_config: dict[str, Any], artifacts_dir: Path
    ) -> GateResult:
        """Check if token usage is within budget."""
        try:
            max_tokens = gate_config.get("max_tokens")
            max_usd = gate_config.get("max_usd")
            tokens_file = artifacts_dir / (
                gate_config.get("tokens_file", "ai-cost.json")
            )

            if not tokens_file.exists():
                return GateResult(
                    gate_name="token_budget",
                    passed=False,
                    message=f"Tokens file not found: {tokens_file}",
                )

            with open(tokens_file, encoding="utf-8") as f:
                data = json.load(f)

            total_tokens = int(data.get("total_estimated_tokens", 0))
            est_usd = float(data.get("estimated_cost_usd", 0.0))

            if max_tokens is not None and total_tokens > int(max_tokens):
                return GateResult(
                    gate_name="token_budget",
                    passed=False,
                    message=f"Token budget exceeded: {total_tokens} > {max_tokens}",
                    details={
                        "tokens": total_tokens,
                        "max_tokens": max_tokens,
                        "usd": est_usd,
                    },
                )

            if max_usd is not None and est_usd > float(max_usd):
                return GateResult(
                    gate_name="token_budget",
                    passed=False,
                    message=f"USD budget exceeded: ${est_usd:.4f} > ${float(max_usd):.4f}",
                    details={
                        "tokens": total_tokens,
                        "usd": est_usd,
                        "max_usd": max_usd,
                    },
                )

            return GateResult(
                gate_name="token_budget",
                passed=True,
                message="Within budget",
                details={
                    "tokens": total_tokens,
                    "usd": est_usd,
                    "max_tokens": max_tokens,
                    "max_usd": max_usd,
                },
            )
        except Exception as e:
            return GateResult(
                gate_name="token_budget",
                passed=False,
                message=f"Token budget gate error: {e}",
            )
        # Try to get actual token usage from cost tracker
        try:
            from .cost_tracker import CostTracker

            tracker = CostTracker()
            daily_usage = tracker.get_daily_usage()
            tokens_used = daily_usage["total_tokens"]

            if tokens_used > max_tokens:
                return GateResult(
                    gate_name="token_budget",
                    passed=False,
                    message=f"Token budget exceeded: {tokens_used} > {max_tokens}",
                    details={"tokens_used": tokens_used, "max_tokens": max_tokens},
                )

            return GateResult(
                gate_name="token_budget",
                passed=True,
                message=f"Token usage within budget: {tokens_used} tokens",
                details={"tokens_used": tokens_used, "max_tokens": max_tokens},
            )

        except ImportError:
            return GateResult(
                gate_name="token_budget",
                passed=True,
                message="Token budget check skipped - cost tracker not available",
            )


class VerifierAdapter:
    """Adapter facade for verifier gates to integrate with workflow execution."""

    def __init__(self, impl: Optional[Verifier] = None):
        self.impl = impl or Verifier()

    def check_gates(
        self, verification_plan: dict[str, Any], ctx: dict[str, Any]
    ) -> dict[str, Any]:
        """Check verification gates and return structured results.

        Expected verification_plan keys: schema, tests, lint, security, diff_limits
        """
        if not self.impl:
            return {"verdict": "pass", "checks": {}}

        # Convert verification plan to gate configs
        gates = []

        if verification_plan.get("tests", False):
            gates.append(
                {
                    "type": "tests_pass",
                    "name": "tests_pass",
                    "test_report": "test_results.json",
                }
            )

        if verification_plan.get("schema", False):
            # Look for artifacts in context
            artifacts = ctx.get("artifacts", [])
            if artifacts:
                gates.append(
                    {
                        "type": "schema_valid",
                        "name": "schema_valid",
                        "artifacts": artifacts,
                    }
                )

        if verification_plan.get("diff_limits"):
            diff_config = verification_plan["diff_limits"]
            gates.append(
                {
                    "type": "diff_limits",
                    "name": "diff_limits",
                    "max_lines": diff_config.get("max_loc", 1000),
                }
            )

        # Check all gates
        artifacts_dir = Path(ctx.get("artifacts_dir", "artifacts"))
        results = self.impl.check_gates(gates, artifacts_dir)

        # Convert to structured response
        all_passed = all(result.passed for result in results)

        return {
            "verdict": "pass" if all_passed else "fail",
            "checks": {
                result.gate_name: {
                    "passed": result.passed,
                    "message": result.message,
                    "details": result.details,
                }
                for result in results
            },
            "summary": {
                "total_gates": len(results),
                "passed": sum(1 for r in results if r.passed),
                "failed": sum(1 for r in results if not r.passed),
            },
        }
