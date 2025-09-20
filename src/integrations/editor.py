from __future__ import annotations

from .process import ProcessRunner
from .registry_tools import probe_binary
from .tools_base import ToolProbe


class VSCodeAdapter:
    def __init__(self, runner: ProcessRunner) -> None:
        self.runner = runner

    def version(self) -> ToolProbe:
        return probe_binary(self.runner, "code", ["--version"])

    def open(self, target: str) -> int:
        return self.runner.run(["code", target]).code

