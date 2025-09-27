#!/usr/bin/env python3
"""
Verifier Adapter

Wraps the Verifier service as a deterministic adapter so workflows can
invoke quality gates and schema checks via the routing system.
"""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Any, Dict, List, Optional

from .base_adapter import AdapterResult, AdapterType, BaseAdapter
from ..verifier import Verifier, GateResult


class VerifierAdapter(BaseAdapter):
    """Adapter exposing artifact verification and gate checks."""

    def __init__(self) -> None:
        super().__init__(
            name="verifier",
            adapter_type=AdapterType.DETERMINISTIC,
            description="Artifact/schema verification and quality gate checks",
        )
        self._verifier = Verifier()

    def execute(
        self,
        step: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None,
        files: Optional[str] = None,
    ) -> AdapterResult:
        self._log_execution_start(step)

        try:
            params = self._extract_with_params(step)
            op = params.get("operation") or params.get("op") or "check_gates"
            emit_paths = self._extract_emit_paths(step)

            if op == "verify_artifact":
                artifact = params.get("artifact")
                schema = params.get("schema")
                if not artifact:
                    return AdapterResult(success=False, error="Missing 'artifact' parameter")

                artifact_path = Path(artifact)
                schema_path = Path(schema) if schema else None
                ok = self._verifier.verify_artifact(artifact_path, schema_path)

                # Optionally emit a simple verification report
                artifacts: List[str] = []
                if emit_paths:
                    report = {
                        "operation": "verify_artifact",
                        "artifact": str(artifact_path),
                        "schema": str(schema_path) if schema_path else None,
                        "valid": ok,
                    }
                    for p in emit_paths:
                        out = Path(p)
                        out.parent.mkdir(parents=True, exist_ok=True)
                        with out.open("w", encoding="utf-8") as f:
                            json.dump(report, f, indent=2)
                        artifacts.append(str(out))

                result = AdapterResult(
                    success=ok,
                    tokens_used=0,
                    artifacts=artifacts,
                    output="artifact valid" if ok else "artifact invalid",
                    metadata={"operation": op, "valid": ok},
                )
                self._log_execution_complete(result)
                return result

            elif op == "check_gates":
                gates = params.get("gates") or []
                artifacts_dir = Path(params.get("artifacts_dir", "artifacts"))
                if not isinstance(gates, list):
                    return AdapterResult(success=False, error="'gates' must be a list")

                results: List[GateResult] = self._verifier.check_gates(gates, artifacts_dir)
                passed = all(r.passed for r in results)

                # Build summary and optionally emit
                summary = {
                    "operation": "check_gates",
                    "passed": passed,
                    "results": [asdict(r) for r in results],
                }
                artifacts: List[str] = []
                if emit_paths:
                    for p in emit_paths:
                        out = Path(p)
                        out.parent.mkdir(parents=True, exist_ok=True)
                        with out.open("w", encoding="utf-8") as f:
                            json.dump(summary, f, indent=2)
                        artifacts.append(str(out))

                result = AdapterResult(
                    success=passed,
                    tokens_used=0,
                    artifacts=artifacts,
                    output="all gates passed" if passed else "one or more gates failed",
                    metadata=summary,
                )
                self._log_execution_complete(result)
                return result

            else:
                return AdapterResult(
                    success=False,
                    error=f"Unknown operation: {op}",
                    metadata={"operation": op},
                )

        except Exception as e:
            return AdapterResult(
                success=False,
                error=f"Verifier operation failed: {e}",
                metadata={"exception_type": type(e).__name__},
            )

    def validate_step(self, step: Dict[str, Any]) -> bool:
        params = self._extract_with_params(step)
        op = params.get("operation") or params.get("op")
        if op == "verify_artifact":
            return bool(params.get("artifact"))
        if op == "check_gates" or op is None:
            return True
        return False

    def estimate_cost(self, step: Dict[str, Any]) -> int:
        # Deterministic operations only
        return 0

    def is_available(self) -> bool:
        # Always available; relies on local JSON and files
        return True

