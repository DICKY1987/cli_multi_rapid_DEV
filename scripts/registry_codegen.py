#!/usr/bin/env python3
"""
Generate registries JSON schema fragments and Python enums from YAML sources.

Inputs:
  - contracts/registries/actions.yaml
  - contracts/registries/actors.yaml
  - contracts/registries/naming.yaml

Outputs:
  - contracts/registries/generated/actions.schema.json (definitions.action_enum)
  - contracts/registries/generated/actors.schema.json  (definitions.actor_enum)
  - packages/apf_common/src/apf_common/registries.py (Enum classes + naming rules)

Fails with non-zero exit if outputs are not up-to-date.
"""
from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Dict, List

try:
    import yaml  # type: ignore
except Exception:  # pragma: no cover
    print("PyYAML required. Install with: pip install pyyaml", file=sys.stderr)
    sys.exit(2)


ROOT = Path(__file__).resolve().parents[1]
REG_DIR = ROOT / "contracts" / "registries"
GEN_DIR = REG_DIR / "generated"
PKG_DIR = ROOT / "packages" / "apf_common" / "src" / "apf_common"
PKG_DIR.mkdir(parents=True, exist_ok=True)
GEN_DIR.mkdir(parents=True, exist_ok=True)


def load_yaml(path: Path) -> Dict:
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def write_if_changed(path: Path, content: str) -> bool:
    old = path.read_text(encoding="utf-8") if path.exists() else None
    if old == content:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return True


def generate_enum_schema(def_name: str, values: List[str], id_uri: str) -> str:
    doc = {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "$id": id_uri,
        "title": f"Registry: {def_name}",
        "type": "object",
        "definitions": {
            def_name: {"type": "string", "enum": values},
        },
    }
    return json.dumps(doc, indent=2, ensure_ascii=False) + "\n"


def generate_python_enums(actions: List[str], actors: List[str], naming: Dict) -> str:
    # Keep simple snake_case to ENUM_NAME values mapping
    def to_member(name: str) -> str:
        return name.upper()

    lines: List[str] = []
    lines.append("from __future__ import annotations")
    lines.append("from enum import Enum")
    lines.append("")
    lines.append("class Action(Enum):")
    for a in actions:
        lines.append(f"    {to_member(a)} = \"{a}\"")
    lines.append("")
    lines.append("class Actor(Enum):")
    for a in actors:
        lines.append(f"    {to_member(a)} = \"{a}\"")
    lines.append("")
    rules = naming.get("rules", {})
    lines.append(f"STEPKEY_PRECISION = {int(rules.get('stepkey_precision', 3))}")
    lines.append(f"ID_PATTERN = r\"{rules.get('id_pattern', '^[A-Z0-9_]{3,20}$')}\"")
    lines.append(f"SEMVERS_PATTERN = r\"{rules.get('semver_pattern', '^\\\\d+\\\\.\\\\d+\\\\.\\\\d+$')}\"")
    lines.append(f"STEPKEY_PATTERN = r\"{rules.get('stepkey_pattern', '^\\\\d+(\\\\.\\\\d+)*$')}\"")
    lines.append("")
    return "\n".join(lines) + "\n"


def main() -> int:
    actions_yaml = load_yaml(REG_DIR / "actions.yaml")
    actors_yaml = load_yaml(REG_DIR / "actors.yaml")
    naming_yaml = load_yaml(REG_DIR / "naming.yaml")

    actions: List[str] = list(dict.fromkeys(actions_yaml.get("actions", [])))
    actors: List[str] = list(dict.fromkeys(actors_yaml.get("actors", [])))
    actions_ver: str = actions_yaml.get("version", "1.0.0")
    actors_ver: str = actors_yaml.get("version", "1.0.0")

    changed = False

    # Generate JSON schema fragments
    actions_json = generate_enum_schema(
        "action_enum", actions, f"https://eafix.io/registries/actions/v{actions_ver}"
    )
    actors_json = generate_enum_schema(
        "actor_enum", actors, f"https://eafix.io/registries/actors/v{actors_ver}"
    )
    changed |= write_if_changed(GEN_DIR / "actions.schema.json", actions_json)
    changed |= write_if_changed(GEN_DIR / "actors.schema.json", actors_json)

    # Generate Python enums
    py_module = generate_python_enums(actions, actors, naming_yaml)
    changed |= write_if_changed(PKG_DIR / "registries.py", py_module)
    # Ensure package is importable
    changed |= write_if_changed(PKG_DIR / "__init__.py", "from .registries import Action, Actor\n")

    if changed:
        print("[registry-codegen] Generated registry outputs.")
        return 1 if "--check" in sys.argv else 0
    print("[registry-codegen] Outputs up-to-date.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

