#!/usr/bin/env python3
"""
Plugin Manager for CLI Orchestrator

Manages plugin discovery, loading, and execution for MOD-005.
"""

import importlib
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    from rich.console import Console

    console = Console()
except ImportError:
    # Fallback to basic print if rich is not available
    class Console:
        def print(self, text, style=None):
            # Remove rich formatting markers
            clean_text = text
            for marker in [
                "[red]",
                "[/red]",
                "[green]",
                "[/green]",
                "[yellow]",
                "[/yellow]",
                "[blue]",
                "[/blue]",
            ]:
                clean_text = clean_text.replace(marker, "")
            print(clean_text)

    console = Console()

from .base_plugin import BasePlugin, PluginResult


class PluginManager:
    """Manages plugins for the verification framework."""

    def __init__(self, plugins_dir: Optional[Path] = None):
        self.plugins_dir = plugins_dir or Path(__file__).parent / "builtin"
        self.plugins: Dict[str, BasePlugin] = {}
        self._discover_plugins()

    def _discover_plugins(self):
        """Discover and load available plugins."""
        if not self.plugins_dir.exists():
            console.print(
                f"[yellow]Plugins directory not found: {self.plugins_dir}[/yellow]"
            )
            return

        # Load builtin plugins
        builtin_plugins = [
            "pytest_plugin",
            "ruff_semgrep_plugin",
            "schema_validate_plugin",
        ]

        for plugin_name in builtin_plugins:
            try:
                # Try absolute import first, then relative
                try:
                    module_path = f"cli_multi_rapid.plugins.builtin.{plugin_name}"
                    module = importlib.import_module(module_path)
                except ImportError:
                    # Fallback to relative import
                    module_path = f".builtin.{plugin_name}"
                    module = importlib.import_module(
                        module_path, package="cli_multi_rapid.plugins"
                    )

                # Look for plugin class (should be named like PytestPlugin)
                class_name = "".join(
                    word.capitalize() for word in plugin_name.split("_")
                )
                if hasattr(module, class_name):
                    plugin_class = getattr(module, class_name)
                    plugin_instance = plugin_class()
                    self.plugins[plugin_instance.name] = plugin_instance
                    console.print(f"Loaded plugin: {plugin_instance.name}")

            except Exception as e:
                console.print(f"Failed to load plugin {plugin_name}: {e}")

    def get_plugin(self, name: str) -> Optional[BasePlugin]:
        """Get a plugin by name."""
        return self.plugins.get(name)

    def list_plugins(self) -> List[str]:
        """List available plugin names."""
        return list(self.plugins.keys())

    def get_plugin_capabilities(self, name: str) -> Optional[Dict[str, Any]]:
        """Get capabilities for a specific plugin."""
        plugin = self.get_plugin(name)
        return plugin.get_capabilities() if plugin else None

    def execute_plugin(
        self,
        name: str,
        config: Dict[str, Any],
        artifacts_dir: Path,
        context: Dict[str, Any],
    ) -> PluginResult:
        """Execute a plugin with timing."""
        plugin = self.get_plugin(name)
        if not plugin:
            return PluginResult(
                plugin_name=name,
                passed=False,
                message=f"Plugin not found: {name}",
                details={"available_plugins": self.list_plugins()},
            )

        # Validate configuration
        try:
            if not plugin.validate_config(config):
                return PluginResult(
                    plugin_name=name,
                    passed=False,
                    message="Plugin configuration validation failed",
                )
        except Exception as e:
            return PluginResult(
                plugin_name=name,
                passed=False,
                message=f"Configuration validation error: {e}",
            )

        # Execute with timing
        start_time = time.perf_counter()
        try:
            result = plugin.execute(config, artifacts_dir, context)
            result.execution_time_ms = (time.perf_counter() - start_time) * 1000
            return result
        except Exception as e:
            execution_time = (time.perf_counter() - start_time) * 1000
            return PluginResult(
                plugin_name=name,
                passed=False,
                message=f"Plugin execution error: {e}",
                execution_time_ms=execution_time,
            )

    def check_plugin_dependencies(self, name: str) -> Dict[str, bool]:
        """Check dependencies for a specific plugin."""
        plugin = self.get_plugin(name)
        return plugin.check_dependencies() if plugin else {}

    def get_plugin_health(self) -> Dict[str, Dict[str, Any]]:
        """Get health status for all plugins."""
        health = {}
        for name, plugin in self.plugins.items():
            dependencies = plugin.check_dependencies()
            all_deps_ok = all(dependencies.values()) if dependencies else True

            health[name] = {
                "available": True,
                "dependencies_ok": all_deps_ok,
                "dependencies": dependencies,
                "capabilities": plugin.get_capabilities(),
                "version": plugin.version,
            }
        return health
