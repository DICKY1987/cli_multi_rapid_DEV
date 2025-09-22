from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict


def guard_requirements_windows(
    requirements_path: str = "requirements.txt",
) -> Dict[str, Any]:
    """Make dev deps Windows-friendly (skip semgrep on win32).

    - If a plain `semgrep` requirement exists, add an environment marker so it
      does not install on Windows hosts where it's unsupported.

    Returns a summary dict with whether a change was made.
    """
    repo_root = Path.cwd()
    req_file = repo_root / requirements_path
    if not req_file.exists():
        return {
            "changed": False,
            "reason": f"requirements file not found: {requirements_path}",
        }

    original = req_file.read_text(encoding="utf-8").splitlines()
    changed = False
    updated_lines = []
    for line in original:
        stripped = line.strip()
        if (
            stripped
            and not stripped.startswith("#")
            and stripped.split("==")[0].split(">=")[0].strip() == "semgrep"
        ):
            # If a marker is already present, keep as-is
            if ";" not in stripped:
                updated_lines.append('semgrep; sys_platform != "win32"')
                changed = True
                continue
        updated_lines.append(line)

    if changed:
        req_file.write_text("\n".join(updated_lines) + "\n", encoding="utf-8")

    return {"changed": changed, "file": str(req_file)}


def cli_smoke() -> Dict[str, Any]:
    """Run lightweight CLI smoke checks via direct function calls."""
    # Ensure src/ is importable for local runs
    src = Path("src").resolve()
    if str(src) not in sys.path:
        sys.path.insert(0, str(src))

    from cli_multi_rapid.cli import greet, sum_numbers  # type: ignore

    hello = greet("Alice")
    s = sum_numbers(2, 3)
    return {"greet": hello, "sum": s}


def orchestrator_status_action() -> Dict[str, Any]:
    """Return orchestrator status snapshot (streams + status report)."""
    # Make project root importable for `workflows` package
    root = Path.cwd()
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

    from workflows.orchestrator import WorkflowOrchestrator  # type: ignore

    orch = WorkflowOrchestrator()
    streams = orch.list_streams()
    status = orch.get_status_report()
    return {"streams": streams, "status": status}
