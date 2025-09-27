import json
import shutil
from pathlib import Path

import typer
from typer.testing import CliRunner


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _copy_workflow(tmp_path: Path) -> Path:
    src = _repo_root() / ".ai" / "workflows" / "CODE_QUALITY.yaml"
    dest_dir = tmp_path / ".ai" / "workflows"
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / "CODE_QUALITY.yaml"
    shutil.copy2(src, dest)
    return dest


def _load_app():
    import sys

    src_path = _repo_root() / "src"
    if str(src_path) not in sys.path:
        sys.path.insert(0, str(src_path))
    from cli_multi_rapid.main import app

    return app


def test_coordination_help_lists_commands():
    app = _load_app()
    runner = CliRunner()
    result = runner.invoke(app, ["coordination", "--help"])
    assert result.exit_code == 0
    # Check key commands are present in help
    out = result.stdout
    for cmd in ["run", "plan", "status", "cancel", "dashboard", "report", "history"]:
        assert cmd in out


def test_coordination_plan_generates_file(tmp_path):
    app = _load_app()
    runner = CliRunner()

    wf = _copy_workflow(tmp_path)
    out_file = tmp_path / "plan.json"
    result = runner.invoke(app, [
        "coordination", "plan", str(wf), "--output", str(out_file)
    ])
    assert result.exit_code == 0, result.stdout
    assert out_file.exists()
    data = json.loads(out_file.read_text(encoding="utf-8"))
    assert isinstance(data, dict)
    assert "execution_order" in data


def test_coordination_run_dry_persists_state(tmp_path):
    app = _load_app()
    runner = CliRunner()

    wf = _copy_workflow(tmp_path)

    # Run in a temp CWD so state/coordination writes inside tmp
    result = runner.invoke(app, [
        "coordination", "run", str(wf), "--dry-run"
    ], env={"PYTHONUTF8": "1"}, catch_exceptions=False)
    assert result.exit_code == 0, result.stdout

    state_dir = tmp_path / "state" / "coordination"
    assert state_dir.exists()
    # Find a saved state file
    files = list(state_dir.glob("coord_*.json"))
    assert files, "expected at least one coordination state file"
