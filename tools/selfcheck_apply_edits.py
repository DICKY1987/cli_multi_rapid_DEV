#!/usr/bin/env python3
import hashlib
import json
import pathlib
import subprocess
import sys


def run(cmd):
    p = subprocess.run(cmd, capture_output=True, text=True)
    return p.returncode, p.stdout, p.stderr


def main():
    root = pathlib.Path(__file__).resolve().parents[1]
    tmp = root / "artifacts" / "_selfcheck"
    tmp.mkdir(parents=True, exist_ok=True)
    f = tmp / "hello.txt"
    f.write_text("a\nB\nc\n", encoding="utf-8")
    sha = hashlib.sha256(f.read_bytes()).hexdigest()
    plan = {
        "metadata": {"pre_edit_checksums": {"artifacts/_selfcheck/hello.txt": sha}},
        "edits": [
            {
                "version": "1.0.0",
                "edit_id": "edit_DEMO0001",
                "file_path": "artifacts/_selfcheck/hello.txt",
                "edit_type": "replace",
                "start_line": 2,
                "end_line": 2,
                "original_content": "B\n",
                "new_content": "b\n",
                "created_at": "2025-01-01T00:00:00Z",
            }
        ],
    }
    plan_path = tmp / "plan.json"
    plan_path.write_text(json.dumps(plan), encoding="utf-8")
    code, out, err = run(
        [sys.executable, str(root / "tools" / "edit_validator_v2.py"), str(plan_path)]
    )
    if code != 0:
        print("validator failed", out, err)
        return code
    code, out, err = run(
        [sys.executable, str(root / "tools" / "apply_edits.py"), str(plan_path)]
    )
    if code != 0:
        print("applier failed", out, err)
        return code
    assert f.read_text(encoding="utf-8") == "a\nb\nc\n"
    print("selfcheck ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
