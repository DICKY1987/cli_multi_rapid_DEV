from __future__ import annotations

from pathlib import Path


def test_gdw_runner_dry_run():
    from lib.gdw_runner import run_gdw

    spec = Path("gdw/git.commit_push.main/v1.0.0/spec.json")
    result = run_gdw(spec, inputs={}, dry_run=True)
    assert result["ok"] is True
    assert result["dry_run"] is True
    assert isinstance(result["workflow_id"], str)

