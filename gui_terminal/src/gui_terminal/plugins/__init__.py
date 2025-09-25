"""Plugin system for GUI Terminal."""

from __future__ import annotations

from typing import Any, Dict, Protocol


class Plugin(Protocol):  # pragma: no cover - interface
    name: str

    def activate(self, context: Dict[str, Any]) -> None: ...
    def deactivate(self) -> None: ...
