#!/usr/bin/env python3
"""
CLI Orchestrator Plugin System

Plugin framework for extensible verification and quality gates.
MOD-005: Verification Framework implementation.
"""

from .base_plugin import BasePlugin, PluginResult
from .plugin_manager import PluginManager

__all__ = ["BasePlugin", "PluginResult", "PluginManager"]
