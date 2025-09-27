#!/usr/bin/env python3
"""
Coordination Config Loader

Loads optional coordination defaults from `.ai/config/coordination.yaml` with
safe fallbacks if the file or fields are missing.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional

import yaml


@dataclass
class CoordinationConfig:
    default_mode: str = "parallel"
    max_parallel_workflows: int = 5
    default_budget: float = 30.0
    timeout_minutes: int = 60

    # Resource limits (not enforced here; used by caller)
    max_memory_mb: int = 2048
    max_cpu_percent: int = 80
    max_file_handles: int = 1000

    # Retry policy
    retry_max_attempts: int = 3
    retry_backoff_seconds: tuple = (1, 5, 15)

    # Security
    security_level: str = "medium"
    isolation_enabled: bool = True
    network_access: bool = False


def _read_yaml(path: Path) -> Dict[str, Any]:
    try:
        if not path.exists():
            return {}
        with path.open("r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
            return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def load_coordination_config(cwd: Optional[Path] = None) -> CoordinationConfig:
    base = Path.cwd() if cwd is None else cwd
    cfg_path = base / ".ai" / "config" / "coordination.yaml"
    data = _read_yaml(cfg_path).get("coordination", {})

    cfg = CoordinationConfig()

    # Map known fields with safe conversions
    cfg.default_mode = str(data.get("default_mode", cfg.default_mode))
    cfg.max_parallel_workflows = int(
        data.get("max_parallel_workflows", cfg.max_parallel_workflows)
    )
    cfg.default_budget = float(data.get("default_budget", cfg.default_budget))
    cfg.timeout_minutes = int(data.get("timeout_minutes", cfg.timeout_minutes))

    # Resource limits
    rl = data.get("resource_limits", {}) or {}
    cfg.max_memory_mb = int(rl.get("max_memory_mb", cfg.max_memory_mb))
    cfg.max_cpu_percent = int(rl.get("max_cpu_percent", cfg.max_cpu_percent))
    cfg.max_file_handles = int(rl.get("max_file_handles", cfg.max_file_handles))

    # Retry policy
    rp = data.get("retry_policy", {}) or {}
    cfg.retry_max_attempts = int(rp.get("max_attempts", cfg.retry_max_attempts))
    backoff = rp.get("backoff_seconds", list(cfg.retry_backoff_seconds))
    try:
        cfg.retry_backoff_seconds = tuple(int(x) for x in backoff)
    except Exception:
        pass

    # Security
    sec = data.get("security", {}) or {}
    cfg.security_level = str(sec.get("default_level", cfg.security_level))
    cfg.isolation_enabled = bool(sec.get("isolation_enabled", cfg.isolation_enabled))
    cfg.network_access = bool(sec.get("network_access", cfg.network_access))

    return cfg

