from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Protocol, runtime_checkable

from .process import CommandResult, ToolError, ProcessRunner


@dataclass
class ToolProbe:
    name: str
    path: Optional[str]
    version: Optional[str]
    ok: bool
    details: Optional[str] = None


@runtime_checkable
class VCS(Protocol):
    def version(self) -> ToolProbe: ...


@runtime_checkable
class Containers(Protocol):
    def version(self) -> ToolProbe: ...


@runtime_checkable
class Editor(Protocol):
    def version(self) -> ToolProbe: ...


@runtime_checkable
class JSRuntime(Protocol):
    def version(self) -> ToolProbe: ...


@runtime_checkable
class AICLI(Protocol):
    def version(self) -> ToolProbe: ...


@runtime_checkable
class PythonQuality(Protocol):
    def run_all(self, fix: bool = False) -> Dict[str, CommandResult]: ...


@runtime_checkable
class PreCommit(Protocol):
    def run_all(self) -> CommandResult: ...


__all__ = [
    "ProcessRunner",
    "CommandResult",
    "ToolError",
    "ToolProbe",
    "VCS",
    "Containers",
    "Editor",
    "JSRuntime",
    "AICLI",
    "PythonQuality",
    "PreCommit",
]

