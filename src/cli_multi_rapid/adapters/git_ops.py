#!/usr/bin/env python3
"""
Git Operations Adapter

Automates simple git operations and emits structured artifacts suitable
for downstream gates and reporting. External integrations (e.g. GitHub PRs)
are mocked by default for safety; enable real operations behind flags.
"""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from .base_adapter import AdapterResult, AdapterType, BaseAdapter


@dataclass
class GitCommandResult:
    success: bool
    stdout: str = ""
    stderr: str = ""
    returncode: int = 0


class GitOpsAdapter(BaseAdapter):
    """Adapter for simple git workflows (branch, commit, PR metadata)."""

    def __init__(self) -> None:
        super().__init__(
            name="git_ops",
            adapter_type=AdapterType.DETERMINISTIC,
            description="Automated git operations (branch/commit/PR metadata)",
        )

    def execute(
        self,
        step: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None,
        files: Optional[str] = None,
    ) -> AdapterResult:
        self._log_execution_start(step)
        try:
            params = self._extract_with_params(step)
            emit_paths = self._extract_emit_paths(step)
            op = params.get("operation", "status")

            if op == "create_branch":
                name = params.get("name") or self._default_branch_name()
                result = self._create_branch(name)
                artifact = self._artifact(
                    "git.branch",
                    {"branch": name, "stdout": result.stdout, "stderr": result.stderr},
                )
            elif op == "commit":
                message = params.get("message", "chore: automated commit")
                add = params.get("add", ["-A"])
                result = self._commit(add, message)
                artifact = self._artifact(
                    "git.commit",
                    {"message": message, "stdout": result.stdout, "stderr": result.stderr},
                )
            elif op == "open_pr":
                title = params.get("title", "Automated PR")
                body = params.get("body", "Opened by git_ops adapter")
                base = params.get("base", "main")
                head = params.get("head") or self._current_branch()
                real = bool(params.get("real", False))

                pr_url = None
                if real:
                    # Try GitHub CLI first
                    try:
                        gh_cmd = [
                            "gh",
                            "pr",
                            "create",
                            "--title",
                            title,
                            "--body",
                            body,
                            "--base",
                            base,
                            "--head",
                            head,
                        ]
                        gh_res = subprocess.run(gh_cmd, capture_output=True, text=True, timeout=60)
                        stdout = (gh_res.stdout or "").strip()
                        if gh_res.returncode == 0 and stdout.startswith("https://"):
                            pr_url = stdout.splitlines()[-1].strip()
                            result = GitCommandResult(True, gh_res.stdout, gh_res.stderr, gh_res.returncode)
                        else:
                            # Fallback to mock if gh failed
                            result = GitCommandResult(False, gh_res.stdout, gh_res.stderr, gh_res.returncode)
                    except Exception as e:
                        result = GitCommandResult(False, "", str(e), 1)
                else:
                    result = GitCommandResult(True)

                if not pr_url:
                    pr_url = f"https://example.com/repo/compare/{base}...{head}#pr"

                artifact = self._artifact(
                    "git.pr",
                    {
                        "title": title,
                        "body": body,
                        "base": base,
                        "head": head,
                        "url": pr_url,
                        "mode": "real" if real else "mock",
                    },
                )
            elif op == "label":
                label = params.get("label", "automation")
                artifact = self._artifact("git.label", {"label": label})
                result = GitCommandResult(True)
            elif op == "assign":
                assignee = params.get("assignee", "")
                artifact = self._artifact("git.assign", {"assignee": assignee})
                result = GitCommandResult(True)
            else:
                artifact = self._artifact("git.status", {"operation": op})
                result = self._git(["status", "--porcelain=v1"])  # non-fatal
                artifact["status"] = result.stdout

            # Write artifact(s)
            artifacts = self._write_artifacts(emit_paths, artifact)
            return AdapterResult(
                success=result.success,
                tokens_used=0,
                artifacts=artifacts,
                output=result.stdout,
                metadata={"operation": op},
            )

        except Exception as e:
            return AdapterResult(success=False, error=f"git_ops failed: {e}")

    def is_available(self) -> bool:  # type: ignore[override]
        try:
            r = subprocess.run(["git", "--version"], capture_output=True, text=True, timeout=5)
            return r.returncode == 0
        except Exception:
            return False

    # Helpers
    def _git(self, args: List[str]) -> GitCommandResult:
        try:
            p = subprocess.run(["git", *args], capture_output=True, text=True, timeout=30)
            return GitCommandResult(p.returncode == 0, p.stdout, p.stderr, p.returncode)
        except Exception as e:
            return GitCommandResult(False, "", str(e), 1)

    def _create_branch(self, name: str) -> GitCommandResult:
        # Create or switch to branch
        res = self._git(["checkout", "-B", name])
        return res

    def _commit(self, add: List[str], message: str) -> GitCommandResult:
        add_res = self._git(["add", *add])
        if not add_res.success:
            return add_res
        return self._git(["commit", "-m", message])

    def _current_branch(self) -> str:
        r = self._git(["rev-parse", "--abbrev-ref", "HEAD"])
        return (r.stdout or "").strip() or "feature/automation"

    def _default_branch_name(self) -> str:
        ts = datetime.utcnow().strftime("%Y%m%d%H%M%S")
        return f"feature/ai-auto-{ts}"

    def _artifact(self, kind: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "timestamp": datetime.utcnow().isoformat(),
            "type": kind,
            **payload,
        }

    def _write_artifacts(self, emit_paths: List[str], obj: Dict[str, Any]) -> List[str]:
        written: List[str] = []
        for p in emit_paths:
            dest = Path(p)
            dest.parent.mkdir(parents=True, exist_ok=True)
            with open(dest, "w", encoding="utf-8") as f:
                json.dump(obj, f, indent=2)
            written.append(str(dest))
        return written
