from __future__ import annotations

from .process import ProcessRunner
from .tools_base import ToolProbe
from .registry_tools import probe_binary


class GitAdapter:
    def __init__(self, runner: ProcessRunner) -> None:
        self.runner = runner

    def version(self) -> ToolProbe:
        return probe_binary(self.runner, "git", ["--version"])

