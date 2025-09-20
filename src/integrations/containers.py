from __future__ import annotations

from .process import ProcessRunner
from .tools_base import ToolProbe
from .registry_tools import probe_binary


class DockerAdapter:
    def __init__(self, runner: ProcessRunner) -> None:
        self.runner = runner

    def version(self) -> ToolProbe:
        return probe_binary(self.runner, "docker", ["--version"])

    def compose_up(self, compose_file: str) -> int:
        res = self.runner.run(["docker", "compose", "-f", compose_file, "up", "-d"])
        return res.code

    def compose_down(self, compose_file: str) -> int:
        res = self.runner.run(["docker", "compose", "-f", compose_file, "down"])
        return res.code

