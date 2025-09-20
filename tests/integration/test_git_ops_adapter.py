from __future__ import annotations

import os
import subprocess
from pathlib import Path

from cli_multi_rapid.adapters.git_ops import GitOpsAdapter


def _run(cmd: list[str], cwd: Path) -> int:
    return subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True).returncode


def test_git_ops_basic_branch_and_commit(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()

    # init repo
    assert _run(["git", "init", "-q"], repo) == 0
    (repo / "README.md").write_text("# Test Repo\n", encoding="utf-8")
    assert _run(["git", "add", "-A"], repo) == 0
    assert _run(["git", "commit", "-m", "chore: init"], repo) == 0

    # switch CWD to repo for adapter
    old = Path.cwd()
    os.chdir(repo)
    try:
        adapter = GitOpsAdapter()
        assert adapter.is_available() is True

        # Create branch
        step_branch = {
            "actor": "git_ops",
            "with": {"operation": "create_branch", "name": "feature/demo"},
            "emits": ["artifacts/git-branch.json"],
        }
        res_b = adapter.execute(step_branch)
        assert res_b.success
        assert len(res_b.artifacts) == 1

        # Commit change
        (repo / "file.txt").write_text("hello", encoding="utf-8")
        step_commit = {
            "actor": "git_ops",
            "with": {"operation": "commit", "message": "feat: add file", "add": ["-A"]},
            "emits": ["artifacts/git-commit.json"],
        }
        res_c = adapter.execute(step_commit)
        assert res_c.success
        assert len(res_c.artifacts) == 1
    finally:
        os.chdir(old)

