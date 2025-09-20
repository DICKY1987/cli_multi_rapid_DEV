from __future__ import annotations

from .process import ProcessRunner
from .registry_tools import probe_binary
from .tools_base import ToolProbe


class NodeAdapter:
    def __init__(self, runner: ProcessRunner) -> None:
        self.runner = runner

    def version(self) -> ToolProbe:
        return probe_binary(self.runner, "node", ["-v"])

    def npm_ci(self, cwd: str) -> int:
        return self.runner.run(["npm", "ci"], cwd=cwd).code

    def run_script(self, script: str, cwd: str) -> int:
        return self.runner.run(["npm", "run", script], cwd=cwd).code

