from __future__ import annotations

import os
import shlex
import subprocess
import sys
import time
from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence


@dataclass
class CommandResult:
    code: int
    stdout: str
    stderr: str
    duration_s: float
    argv: List[str]
    cwd: Optional[str] = None
    env: Optional[Dict[str, str]] = None


class ToolError(RuntimeError):
    pass


class ProcessRunner:
    """Simple cross-platform process runner with dry-run support.

    - Uses `subprocess.Popen` to avoid shell-specific quoting issues.
    - On Windows, prefers invoking `.exe`/`.cmd` directly when provided.
    - Returns a structured `CommandResult` with timings and captured IO.
    """

    def __init__(self, dry_run: bool = False, timeout_s: Optional[float] = None) -> None:
        self.dry_run = dry_run
        self.timeout_s = timeout_s

    def run(
        self,
        argv: Sequence[str],
        cwd: Optional[str] = None,
        env: Optional[Dict[str, str]] = None,
        check: bool = False,
        text: bool = True,
    ) -> CommandResult:
        cmd = list(argv)
        start = time.time()
        if self.dry_run:
            # Do not execute; return a zero-code result describing intent
            return CommandResult(
                code=0,
                stdout="",
                stderr="",
                duration_s=0.0,
                argv=cmd,
                cwd=cwd,
                env=env,
            )

        proc_env = os.environ.copy()
        if env:
            proc_env.update(env)

        try:
            completed = subprocess.run(
                cmd,
                cwd=cwd,
                env=proc_env,
                capture_output=True,
                text=text,
                timeout=self.timeout_s,
                shell=False,
            )
        except subprocess.TimeoutExpired as exc:  # pragma: no cover (rare in unit tests)
            raise ToolError(f"Command timed out: {' '.join(map(shlex.quote, cmd))}") from exc
        except FileNotFoundError as exc:
            raise ToolError(f"Command not found: {cmd[0]}") from exc

        dur = time.time() - start
        res = CommandResult(
            code=completed.returncode,
            stdout=completed.stdout or "",
            stderr=completed.stderr or "",
            duration_s=dur,
            argv=cmd,
            cwd=cwd,
            env=env,
        )

        if check and res.code != 0:
            raise ToolError(
                f"Command failed ({res.code}): {' '.join(map(shlex.quote, cmd))}\n{res.stderr}"
            )
        return res

