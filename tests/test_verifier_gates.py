import json
from pathlib import Path

from cli_multi_rapid.verifier import Verifier, VerifierAdapter


def write_json(path: Path, data: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def test_tests_pass_gate(tmp_path: Path) -> None:
    artifacts = tmp_path / "artifacts"
    # success=True variant
    write_json(artifacts / "test_results.json", {"success": True})
    v = Verifier()
    res = v.check_gates([{"type": "tests_pass"}], artifacts)
    assert res[0].passed is True
    # failed summary variant
    write_json(artifacts / "test_results.json", {"summary": {"failed": 2}})
    res2 = v.check_gates([{"type": "tests_pass"}], artifacts)
    assert res2[0].passed is False


def test_diff_limits_gate(tmp_path: Path) -> None:
    artifacts = tmp_path / "artifacts"
    v = Verifier()
    # within limit
    write_json(artifacts / "diff_stats.json", {"total_lines": 10})
    ok = v.check_gates([{"type": "diff_limits", "max_lines": 50}], artifacts)[0]
    assert ok.passed is True
    # exceed limit
    write_json(artifacts / "diff_stats.json", {"total_lines": 100})
    bad = v.check_gates([{"type": "diff_limits", "max_lines": 50}], artifacts)[0]
    assert bad.passed is False


def test_schema_valid_gate(tmp_path: Path) -> None:
    artifacts = tmp_path / "artifacts"
    v = Verifier()
    # Create a valid artifact and matching schema
    art = {"timestamp": "2025-09-21T00:00:00Z", "type": "ok", "n": 1}
    sch = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "type": "object",
        "required": ["timestamp", "type"],
        "properties": {"timestamp": {"type": "string"}, "type": {"type": "string"}, "n": {"type": "number"}},
    }
    write_json(artifacts / "a.json", art)
    schema_file = tmp_path / "schema.json"
    write_json(schema_file, sch)
    gates = [{"type": "schema_valid", "artifacts": ["a.json"], "schema_mapping": {"a.json": str(schema_file)}}]
    res = v.check_gates(gates, artifacts)
    assert res[0].passed is True
    # Make it invalid
    write_json(artifacts / "a.json", {"timestamp": 1, "type": "ok"})
    res2 = v.check_gates(gates, artifacts)
    assert res2[0].passed is False


def test_token_budget_gate(tmp_path: Path) -> None:
    artifacts = tmp_path / "artifacts"
    v = Verifier()
    # Within limits
    write_json(artifacts / "ai-cost.json", {"total_estimated_tokens": 100, "estimated_cost_usd": 0.05})
    ok = v.check_gates([{"type": "token_budget", "max_tokens": 200, "max_usd": 1.0}], artifacts)[0]
    assert ok.passed is True
    # Exceed tokens
    write_json(artifacts / "ai-cost.json", {"total_estimated_tokens": 300, "estimated_cost_usd": 0.05})
    bad_tokens = v.check_gates([{"type": "token_budget", "max_tokens": 200}], artifacts)[0]
    assert bad_tokens.passed is False
    # Exceed usd
    write_json(artifacts / "ai-cost.json", {"total_estimated_tokens": 100, "estimated_cost_usd": 2.0})
    bad_usd = v.check_gates([{"type": "token_budget", "max_usd": 1.0}], artifacts)[0]
    assert bad_usd.passed is False


def test_verifier_adapter(tmp_path: Path) -> None:
    artifacts = tmp_path / "artifacts"
    write_json(artifacts / "test_results.json", {"success": True})
    write_json(artifacts / "ai-cost.json", {"total_estimated_tokens": 1, "estimated_cost_usd": 0.01})
    v = Verifier()
    adapter = VerifierAdapter(v)
    plan = {"tests": True, "schema": False, "diff_limits": {"max_loc": 100}}
    result = adapter.check_gates(plan, {"artifacts_dir": str(artifacts)})
    assert result["verdict"] in {"pass", "fail"}
    assert "tests_pass" in result["checks"]

