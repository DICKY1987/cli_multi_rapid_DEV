from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

import yaml  # type: ignore

from .process import ProcessRunner, ToolError
from .tools_base import ToolProbe


TOOLS_CONFIG_ENV = "CLI_MR_TOOLS_CONFIG"


@dataclass
class ToolSelection:
    vcs: str
    containers: str
    editor: str
    js_runtime: str
    ai_cli: str
    python_quality: Dict[str, bool]
    precommit: bool
    paths: Dict[str, Optional[str]]


def _repo_root() -> Path:
    # Assume this file is in src/integrations; repo root is three levels up
    here = Path(__file__).resolve()
    for _ in range(4):
        if (here / "pyproject.toml").exists():
            return here
        here = here.parent
    # Fallback to cwd
    return Path(os.getcwd())


def load_config() -> ToolSelection:
    root = _repo_root()
    default_cfg_path = os.environ.get(TOOLS_CONFIG_ENV) or str(root / "config" / "tools.yaml")
    if os.path.exists(default_cfg_path):
        with open(default_cfg_path, "r", encoding="utf-8") as f:
            cfg = yaml.safe_load(f) or {}
    else:
        cfg = {}

    # Defaults with opt-in booleans
    selection = ToolSelection(
        vcs=cfg.get("vcs", "git"),
        containers=cfg.get("containers", "docker"),
        editor=cfg.get("editor", "vscode"),
        js_runtime=cfg.get("js_runtime", "node"),
        ai_cli=cfg.get("ai_cli", "openai"),
        python_quality=cfg.get(
            "python_quality",
            {"ruff": True, "mypy": True, "bandit": True, "semgrep": True},
        ),
        precommit=bool(cfg.get("precommit", True)),
        paths=cfg.get("paths", {}),
    )
    return selection


def _extract_version(output: str) -> Optional[str]:
    m = re.search(r"\b(v?\d+\.\d+\.\d+[^\s]*)", output)
    return m.group(1) if m else None


def probe_binary(runner: ProcessRunner, binary: str, args: List[str]) -> ToolProbe:
    try:
        res = runner.run([binary] + args)
        version = _extract_version(res.stdout or res.stderr)
        return ToolProbe(name=binary, path=binary, version=version, ok=res.code == 0)
    except ToolError as e:
        return ToolProbe(name=binary, path=None, version=None, ok=False, details=str(e))


def detect_all(runner: ProcessRunner) -> Dict[str, ToolProbe]:
    sel = load_config()

    # Candidate paths for Windows defaults; env PATH will be used if no explicit path provided
    paths = {
        "git": sel.paths.get("git") or "git",
        "gh": sel.paths.get("gh") or "gh",
        "docker": sel.paths.get("docker") or "docker",
        "code": sel.paths.get("code") or "code",
        "node": sel.paths.get("node") or "node",
        "npx": sel.paths.get("npx") or "npx",
        "openai": sel.paths.get("openai") or "openai",
        "claude": sel.paths.get("claude") or "claude",
        "pre-commit": sel.paths.get("pre_commit") or "pre-commit",
        "ruff": sel.paths.get("ruff") or "ruff",
        "mypy": sel.paths.get("mypy") or "mypy",
        "bandit": sel.paths.get("bandit") or "bandit",
        "semgrep": sel.paths.get("semgrep") or "semgrep",
    }

    probes: Dict[str, ToolProbe] = {}

    probes["git"] = probe_binary(runner, paths["git"], ["--version"])
    probes["gh"] = probe_binary(runner, paths["gh"], ["--version"])
    probes["docker"] = probe_binary(runner, paths["docker"], ["--version"])
    probes["code"] = probe_binary(runner, paths["code"], ["--version"])
    probes["node"] = probe_binary(runner, paths["node"], ["-v"])
    probes["npx"] = probe_binary(runner, paths["npx"], ["--version"])

    # AI CLIs: allow either
    if sel.ai_cli == "openai":
        # Prefer npx openai when direct binary missing; simple version check
        if probes["openai"].ok if "openai" in paths else False:
            probes["openai"] = probe_binary(runner, paths.get("openai", "openai"), ["--version"])
        else:
            # Try via npx
            probes["openai"] = probe_binary(runner, paths["npx"], ["openai", "--version"])  # type: ignore[arg-type]
    else:
        probes["claude"] = probe_binary(runner, paths["claude"], ["--version"])

    probes["pre-commit"] = probe_binary(runner, paths["pre-commit"], ["--version"])
    probes["ruff"] = probe_binary(runner, paths["ruff"], ["--version"])
    probes["mypy"] = probe_binary(runner, paths["mypy"], ["--version"])
    probes["bandit"] = probe_binary(runner, paths["bandit"], ["--version"])
    probes["semgrep"] = probe_binary(runner, paths["semgrep"], ["--version"])

    return probes

