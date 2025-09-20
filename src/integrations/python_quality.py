from __future__ import annotations

from typing import Dict, List, Optional

from .process import CommandResult, ProcessRunner


class QualitySuite:
    def __init__(self, runner: ProcessRunner) -> None:
        self.runner = runner

    def ruff(self, fix: bool = False, paths: Optional[List[str]] = None) -> CommandResult:
        args = ["ruff", "check"]
        if fix:
            args.append("--fix")
        args += paths or ["."]
        return self.runner.run(args)

    def mypy(self, targets: Optional[List[str]] = None) -> CommandResult:
        args = ["mypy"] + (targets or ["src"])  # rely on mypy.ini if present
        return self.runner.run(args)

    def bandit(self, target: str = "src") -> CommandResult:
        args = ["bandit", "-q", "-r", target]
        return self.runner.run(args)

    def semgrep(self, target: str = ".") -> CommandResult:
        args = ["semgrep", "--error", "--config", "auto", target]
        return self.runner.run(args)

    def run_all(self, fix: bool = False) -> Dict[str, CommandResult]:
        results: Dict[str, CommandResult] = {}
        results["ruff"] = self.ruff(fix=fix)
        results["mypy"] = self.mypy()
        results["bandit"] = self.bandit()
        results["semgrep"] = self.semgrep()
        return results

