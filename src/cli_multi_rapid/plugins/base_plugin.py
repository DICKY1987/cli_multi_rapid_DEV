#!/usr/bin/env python3
"""
Base Plugin Interface for CLI Orchestrator

Defines the plugin interface and common structures for MOD-005.
"""

import abc
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List


@dataclass
class PluginResult:
    """Result of a plugin execution."""

    plugin_name: str
    passed: bool
    message: str
    details: Dict[str, Any] = None
    artifacts_created: List[str] = None
    execution_time_ms: float = 0.0

    def __post_init__(self):
        if self.details is None:
            self.details = {}
        if self.artifacts_created is None:
            self.artifacts_created = []


class BasePlugin(abc.ABC):
    """Base class for all CLI Orchestrator plugins."""

    def __init__(self, name: str, version: str = "1.0.0"):
        self.name = name
        self.version = version

    @abc.abstractmethod
    def get_capabilities(self) -> Dict[str, Any]:
        """Return plugin capabilities and metadata."""
        pass

    @abc.abstractmethod
    def validate_config(self, config: Dict[str, Any]) -> bool:
        """Validate plugin configuration."""
        pass

    @abc.abstractmethod
    def execute(
        self, config: Dict[str, Any], artifacts_dir: Path, context: Dict[str, Any]
    ) -> PluginResult:
        """Execute the plugin with given configuration."""
        pass

    def get_required_tools(self) -> List[str]:
        """Return list of required external tools/dependencies."""
        return []

    def check_dependencies(self) -> Dict[str, bool]:
        """Check if all dependencies are available."""
        dependencies = {}
        for tool in self.get_required_tools():
            dependencies[tool] = self._check_tool_available(tool)
        return dependencies

    def _check_tool_available(self, tool: str) -> bool:
        """Check if a tool is available in PATH."""
        import shutil

        return shutil.which(tool) is not None
