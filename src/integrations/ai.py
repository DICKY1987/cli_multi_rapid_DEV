from __future__ import annotations

import os
from typing import List

from .process import ProcessRunner
from .registry_tools import probe_binary
from .tools_base import ToolProbe


class OpenAIAdapter:
    def __init__(self, runner: ProcessRunner) -> None:
        self.runner = runner

    def version(self) -> ToolProbe:
        return probe_binary(self.runner, "npx", ["openai", "--version"])  # prefer npx wrapper

    def run(self, args: List[str]) -> int:
        return self.runner.run(["npx", "openai"] + args).code


class ClaudeAdapter:
    def __init__(self, runner: ProcessRunner) -> None:
        self.runner = runner

    def version(self) -> ToolProbe:
        return probe_binary(self.runner, "claude", ["--version"])

    def run(self, args: List[str]) -> int:
        return self.runner.run(["claude"] + args).code

