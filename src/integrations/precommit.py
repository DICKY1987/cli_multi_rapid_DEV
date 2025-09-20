from __future__ import annotations

from .process import CommandResult, ProcessRunner


class PreCommitRunner:
    def __init__(self, runner: ProcessRunner) -> None:
        self.runner = runner

    def install(self) -> CommandResult:
        return self.runner.run(["pre-commit", "install"])

    def run_all(self) -> CommandResult:
        return self.runner.run(["pre-commit", "run", "--all-files"])

