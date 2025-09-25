from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

try:
    import yaml  # type: ignore
except Exception:  # pragma: no cover
    yaml = None  # type: ignore


@dataclass
class ToolInfo:
    name: str
    capabilities: List[str]
    cost_hint: float = 0.0
    status: str = "unknown"


def _load_tools_cfg(path: Path) -> Dict[str, ToolInfo]:
    if not path.exists():
        return {}
    if yaml is None:  # pragma: no cover
        return {}
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    tools: Dict[str, ToolInfo] = {}
    for t in data.get("tools", []):
        tools[t.get("name")] = ToolInfo(
            name=t.get("name"),
            capabilities=list(t.get("capabilities", [])),
            cost_hint=float(t.get("cost_hint", 0.0)),
        )
    return tools


def _load_health(path: Path) -> Dict[str, str]:
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    statuses: Dict[str, str] = {}
    for rec in data.get("tools", []):
        statuses[rec.get("name")] = rec.get("status", "unknown")
    return statuses


def _load_failovers(path: Path) -> Dict[str, List[str]]:
    if not path.exists() or yaml is None:
        return {}
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    result: Dict[str, List[str]] = {}
    for cap, spec in (data.get("capability_failover_maps") or {}).items():
        chain = spec.get("fallback_chain") or []
        result[cap] = [item.get("tool") for item in chain if item.get("tool")]
    return result


def select_tool_for_capability(
    capability: str,
    tools_cfg: Path = Path("config/tools.yaml"),
    health_json: Path = Path("state/tool_health.json"),
    failover_maps: Path = Path("config/failover_maps.yaml"),
) -> Optional[str]:
    """Select the cheapest healthy tool providing the capability, falling back per failover maps.

    Returns a tool name or None if no suitable tool is found.
    """
    tools = _load_tools_cfg(tools_cfg)
    health = _load_health(health_json)
    for name, status in health.items():
        if name in tools:
            tools[name].status = status

    # Candidates by capability
    candidates = [t for t in tools.values() if capability in t.capabilities and t.status == "healthy"]
    if candidates:
        candidates.sort(key=lambda t: t.cost_hint)
        return candidates[0].name

    # Use failover chain if no healthy capability providers
    chain = _load_failovers(failover_maps).get(capability, [])
    chain_candidates = [tools[n] for n in chain if n in tools]
    chain_candidates = [t for t in chain_candidates if tools.get(t.name, t).status == "healthy"]
    if chain_candidates:
        chain_candidates.sort(key=lambda t: t.cost_hint)
        return chain_candidates[0].name

    return None


def estimate_plan_cost(
    plan_steps: List[Dict[str, Any]],
    capability_field: str = "capability",
    tools_cfg: Path = Path("config/tools.yaml"),
    health_json: Path = Path("state/tool_health.json"),
) -> float:
    """Estimate plan cost by summing chosen tool cost hints per step capability."""
    tools = _load_tools_cfg(tools_cfg)
    health = _load_health(health_json)
    for name, status in health.items():
        if name in tools:
            tools[name].status = status

    total = 0.0
    for step in plan_steps:
        cap = step.get(capability_field)
        if not cap:
            continue
        tool = select_tool_for_capability(cap, tools_cfg, health_json)
        if tool and tool in tools:
            total += max(0.0, tools[tool].cost_hint)
    return round(total, 4)

