#!/usr/bin/env python3
"""CLI Orchestrator Verifier

Implements gate-based quality control system for validating artifacts,
checking test results, and enforcing quality standards.
"""

from __future__ import annotations

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
    details: dict[str, Any] | None = None

    def __post_init__(self) -> None:  # pragma: no cover - trivial
        if self.details is None:
            self.details = {}


class Verifier:
    """Validates artifacts and enforces quality gates."""

    def verify_artifact(
        self, artifact_file: Path, schema_file: Optional[Path] = None
    ) -> bool:
        """Verify an artifact against its JSON schema.

        Basic validation requires 'timestamp' and 'type' fields when schema is omitted.
        """
        try:
            if not artifact_file.exists():
                console.print(f"[red]Artifact file not found: {artifact_file}[/red]")
                return False

            with open(artifact_file, encoding="utf-8") as f:
                artifact = json.load(f)

            if schema_file and schema_file.exists():
                return self._validate_against_schema(artifact, schema_file)
            return self._basic_validation(artifact)
        except Exception as e:  # pragma: no cover - defensive
            console.print(f"[red]Artifact verification error: {e}[/red]")
            return False

    def _validate_against_schema(self, artifact: dict[str, Any], schema_file: Path) -> bool:
        try:
            import jsonschema  # lazy import

            with open(schema_file, encoding="utf-8") as f:
                schema = json.load(f)
            jsonschema.validate(artifact, schema)
            return True
        except Exception:
            return False

    def _basic_validation(self, artifact: dict[str, Any]) -> bool:
        required_fields = ["timestamp", "type"]
        return all(field in artifact for field in required_fields)

    def check_gates(self, gates: list[dict[str, Any]], artifacts_dir: Path = Path("artifacts")) -> list[GateResult]:
        """Check multiple quality gates.

        Supported gate types: tests_pass, diff_limits, schema_valid, token_budget
        """
        results: list[GateResult] = []
        for gate_config in gates:
            gate_type = gate_config.get("type", "unknown")
            gate_name = gate_config.get("name", gate_type)
            try:
                if gate_type == "tests_pass":
                    result = self._check_tests_pass_gate(gate_config, artifacts_dir)
                elif gate_type == "diff_limits":
                    result = self._check_diff_limits_gate(gate_config, artifacts_dir)
                elif gate_type == "schema_valid":
                    result = self._check_schema_valid_gate(gate_config, artifacts_dir)
                elif gate_type == "token_budget":
                    result = self._check_token_budget_gate(gate_config, artifacts_dir)
                else:
                    result = GateResult(gate_name=gate_name, passed=False, message=f"Unknown gate type: {gate_type}")
            except Exception as e:  # pragma: no cover - defensive
                result = GateResult(gate_name=gate_name, passed=False, message=f"Gate check error: {e}")
            results.append(result)
        return results

    def _check_tests_pass_gate(self, gate_config: dict[str, Any], artifacts_dir: Path) -> GateResult:
        """Check if test results indicate passing tests.

        Expects a JSON report file with either:
        - {"success": true}
        - {"summary": {"failed": 0}}
        """
        report_name = gate_config.get("test_report", "test_results.json")
        report_file = artifacts_dir / report_name
        if not report_file.exists():
            return GateResult("tests_pass", False, f"Test report not found: {report_file}")
        try:
            data = json.loads(report_file.read_text(encoding="utf-8"))
            if isinstance(data, dict) and data.get("success") is True:
                return GateResult("tests_pass", True, "Tests passed")
            failed = int(data.get("summary", {}).get("failed", 1))
            passed = failed == 0
            return GateResult("tests_pass", passed, "Tests passed" if passed else "Tests failed", details={"failed": failed})
        except Exception as e:
            return GateResult("tests_pass", False, f"Invalid test report: {e}")

    def _check_diff_limits_gate(self, gate_config: dict[str, Any], artifacts_dir: Path) -> GateResult:
        """Check if diff size is within limits.

        Reads artifacts/diff_stats.json with {"total_lines": N} if present.
        """
        max_lines = int(gate_config.get("max_lines", 1000))
        stats_file = artifacts_dir / gate_config.get("diff_stats", "diff_stats.json")
        if not stats_file.exists():
            return GateResult("diff_limits", True, "No diff stats; skipping")
        try:
            data = json.loads(stats_file.read_text(encoding="utf-8"))
            total = int(data.get("total_lines", 0))
            if total > max_lines:
                return GateResult("diff_limits", False, f"Diff too large: {total} > {max_lines}", details={"total_lines": total, "max_lines": max_lines})
            return GateResult("diff_limits", True, "Diff within limits", details={"total_lines": total, "max_lines": max_lines})
        except Exception as e:
            return GateResult("diff_limits", False, f"Invalid diff stats: {e}")

    def _check_schema_valid_gate(self, gate_config: dict[str, Any], artifacts_dir: Path) -> GateResult:
        """Validate a list of artifacts against schemas if provided.

        gate_config may include:
          - artifacts: list of relative paths under artifacts_dir
          - schema_mapping: {artifact_path: schema_path}
          - schema_dir: base directory for schema lookup
        """
        artifacts: list[str] = gate_config.get("artifacts", [])
        mapping: dict[str, str] | None = gate_config.get("schema_mapping")
        schema_dir = Path(gate_config.get("schema_dir", ".ai/schemas"))
        if not artifacts:
            return GateResult("schema_valid", True, "No artifacts to validate")

        details: dict[str, Any] = {}
        all_ok = True
        for rel in artifacts:
            art_path = artifacts_dir / rel
            schema_file: Optional[Path] = None
            if mapping and rel in mapping:
                schema_file = Path(mapping[rel])
            elif schema_dir.exists():
                # simple heuristic: use a single schema if present in mapping-like config
                # otherwise basic validation
                pass
            ok = self.verify_artifact(art_path, schema_file)
            details[str(art_path)] = ok
            all_ok = all_ok and ok

        return GateResult("schema_valid", all_ok, "All artifacts valid" if all_ok else "One or more artifacts invalid", details=details)

    def _check_token_budget_gate(self, gate_config: dict[str, Any], artifacts_dir: Path) -> GateResult:
        """Check if token usage is within budget.

        Reads artifacts/ai-cost.json with keys:
          - total_estimated_tokens
          - estimated_cost_usd
        and compares with gate_config max_tokens / max_usd.
        """
        max_tokens = gate_config.get("max_tokens")
        max_usd = gate_config.get("max_usd")
        tokens_file = artifacts_dir / gate_config.get("tokens_file", "ai-cost.json")
        if not tokens_file.exists():
            return GateResult("token_budget", False, f"Tokens file not found: {tokens_file}")
        try:
            data = json.loads(tokens_file.read_text(encoding="utf-8"))
            total_tokens = int(data.get("total_estimated_tokens", 0))
            est_usd = float(data.get("estimated_cost_usd", 0.0))
            if max_tokens is not None and total_tokens > int(max_tokens):
                return GateResult("token_budget", False, f"Token budget exceeded: {total_tokens} > {max_tokens}", details={"tokens": total_tokens, "max_tokens": max_tokens, "usd": est_usd})
            if max_usd is not None and est_usd > float(max_usd):
                return GateResult("token_budget", False, f"USD budget exceeded: ${est_usd:.4f} > ${float(max_usd):.4f}", details={"tokens": total_tokens, "usd": est_usd, "max_usd": max_usd})
            return GateResult("token_budget", True, "Within budget", details={"tokens": total_tokens, "usd": est_usd, "max_tokens": max_tokens, "max_usd": max_usd})
        except Exception as e:
            return GateResult("token_budget", False, f"Token budget gate error: {e}")


class VerifierAdapter:
    """Adapter facade to convert higher-level verification plans to gate checks."""

    def __init__(self, impl: Optional[Verifier] = None) -> None:
        self.impl = impl or Verifier()

    def check_gates(self, verification_plan: dict[str, Any], ctx: dict[str, Any]) -> dict[str, Any]:
        gates: list[dict[str, Any]] = []

        if verification_plan.get("tests", False):
            gates.append({"type": "tests_pass", "name": "tests_pass", "test_report": "test_results.json"})

        if verification_plan.get("schema", False):
            artifacts = ctx.get("artifacts", [])
            if artifacts:
                gates.append({"type": "schema_valid", "name": "schema_valid", "artifacts": artifacts})

        if verification_plan.get("diff_limits"):
            diff_cfg = verification_plan["diff_limits"]
            gates.append({"type": "diff_limits", "name": "diff_limits", "max_lines": diff_cfg.get("max_loc", 1000)})

        artifacts_dir = Path(ctx.get("artifacts_dir", "artifacts"))
        results = self.impl.check_gates(gates, artifacts_dir)

        all_passed = all(r.passed for r in results)
        return {
            "verdict": "pass" if all_passed else "fail",
            "checks": {r.gate_name: {"passed": r.passed, "message": r.message, "details": r.details} for r in results},
            "summary": {"total_gates": len(results), "passed": sum(1 for r in results if r.passed), "failed": sum(1 for r in results if not r.passed)},
        }

