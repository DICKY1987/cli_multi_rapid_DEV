"""
Plugin system for CLI Multi-Rapid GUI Terminal
"""

from .base_plugin import BasePlugin
from .plugin_manager import PluginManager

__all__ = ["PluginManager", "BasePlugin"]
