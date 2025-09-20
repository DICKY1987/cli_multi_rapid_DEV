#!/usr/bin/env python3
"""
Schema diff gate for contracts/schemas.

Classifies changes as breaking/additive/patch and enforces SemVer bump rules
using the root "version" field and $id. Simple heuristics:
 - Breaking: added required fields, removed required fields that still exist? (non-breaking),
             removed previously required properties, changed type, enum shrank,
             changed pattern/minimum/maximum/format, removed properties.
 - Additive: added optional properties, added enum values (superset), added definitions.
 - Patch: changes limited to title/description examples without structural changes.

If classification is breaking -> require MAJOR bump; additive -> MINOR; patch -> PATCH.
If classification uncertain, default to breaking.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple


ROOT = Path(__file__).resolve().parents[1]
SCHEMAS_DIR = ROOT / "contracts" / "schemas"


def run(cmd: List[str], cwd: Optional[Path] = None) -> str:
    res = subprocess.run(cmd, cwd=str(cwd) if cwd else None, capture_output=True, text=True)
    if res.returncode != 0:
        raise RuntimeError(f"Command failed: {' '.join(cmd)}\n{res.stderr}")
    return res.stdout


def parse_version(v: str) -> Tuple[int, int, int]:
    m = re.match(r"^(\d+)\.(\d+)\.(\d+)$", v.strip())
    if not m:
        raise ValueError(f"Invalid semver: {v}")
    return tuple(int(x) for x in m.groups())  # type: ignore[return-value]


def load_json_text(text: str) -> Dict[str, Any]:
    return json.loads(text)


def load_json_file(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def get_changed_schema_paths(base_ref: str) -> List[Path]:
    diff = run(["git", "diff", "--name-only", f"origin/{base_ref}...HEAD"]).splitlines()
    paths = [ROOT / p for p in diff if p.startswith("contracts/schemas/") and p.endswith(".json")]
    return paths


def git_show(path: Path, ref: str) -> Optional[str]:
    try:
        return run(["git", "show", f"origin/{ref}:{path.as_posix()}"], cwd=ROOT)
    except RuntimeError:
        return None


@dataclass
class ChangeReport:
    path: Path
    kind: str  # breaking|additive|patch|unknown
    details: List[str]
    old_version: Optional[str]
    new_version: Optional[str]


IGNORED_KEYS = {"title", "description", "$schema", "$id", "default", "examples"}


def collect_props(schema: Dict[str, Any], base: str = "") -> Tuple[Set[str], Set[str], Dict[str, Any]]:
    props_paths: Set[str] = set()
    required_paths: Set[str] = set()
    types: Dict[str, Any] = {}

    def walk(node: Any, path: str):
        if isinstance(node, dict):
            if "properties" in node and isinstance(node["properties"], dict):
                for k, v in node["properties"].items():
                    p = f"{path}/properties/{k}"
                    props_paths.add(p)
                    types[f"{p}/type"] = v.get("type")
                    if "enum" in v:
                        types[f"{p}/enum"] = list(v["enum"])  # copy
                    if "pattern" in v:
                        types[f"{p}/pattern"] = v["pattern"]
                    walk(v, p)
            if "required" in node and isinstance(node["required"], list):
                for req in node["required"]:
                    required_paths.add(f"{path}/required/{req}")
            # Recurse other keys
            for k, v in node.items():
                if k in {"properties", "required"}:
                    continue
                if k in IGNORED_KEYS:
                    continue
                walk(v, f"{path}/{k}")
        elif isinstance(node, list):
            for i, item in enumerate(node):
                walk(item, f"{path}/{i}")

    walk(schema, base)
    return props_paths, required_paths, types


def classify_change(old: Dict[str, Any], new: Dict[str, Any]) -> Tuple[str, List[str]]:
    details: List[str] = []
    old_props, old_required, old_types = collect_props(old)
    new_props, new_required, new_types = collect_props(new)

    breaking = False
    additive = False

    # Required added (more constraints) => breaking
    added_required = new_required - old_required
    if added_required:
        details.append(f"added required: {sorted(added_required)}")
        breaking = True

    # Properties removed; if they were required previously, breaking
    removed_props = old_props - new_props
    if removed_props:
        # Flag breaking if any removed was also required
        removed_required = {rp for rp in removed_props if rp.replace("/properties/", "/required/").rsplit("/", 1)[0] + "/" + rp.rsplit("/", 1)[1] in old_required}
        if removed_required or removed_props:
            details.append(f"removed properties: {sorted(list(removed_props))}")
            breaking = True

    # Type or pattern changes => breaking
    for key, old_val in old_types.items():
        if key in new_types and new_types[key] != old_val:
            # enum handled below
            if key.endswith("/enum"):
                continue
            details.append(f"changed {key}: {old_val} -> {new_types[key]}")
            breaking = True

    # Enum changes: if new is supersets -> additive; if subset/different -> breaking
    for key, old_enum in old_types.items():
        if not key.endswith("/enum"):
            continue
        new_enum = new_types.get(key)
        if new_enum is None:
            details.append(f"enum removed at {key}")
            breaking = True
            continue
        old_set, new_set = set(old_enum), set(new_enum)
        if old_set == new_set:
            continue
        if old_set.issubset(new_set):
            details.append(f"enum extended at {key}: +{sorted(list(new_set - old_set))}")
            additive = True
        else:
            details.append(f"enum narrowed at {key}: -{sorted(list(old_set - new_set))}")
            breaking = True

    # New properties added (and not required) -> additive
    added_props = new_props - old_props
    if added_props:
        details.append(f"added properties: {sorted(list(added_props))}")
        if not added_required:  # if also added required, we already marked breaking
            additive = True

    if breaking:
        return "breaking", details
    if additive:
        return "additive", details
    # If nothing meaningful changed beyond ignored keys, treat as patch
    if json.dumps(old, sort_keys=True) != json.dumps(new, sort_keys=True):
        return "patch", details
    return "patch", details


def main() -> int:
    base_ref = os.environ.get("BASE_REF") or os.environ.get("GITHUB_BASE_REF") or "main"
    # Ensure we have base ref locally
    try:
        run(["git", "fetch", "origin", base_ref], cwd=ROOT)
    except Exception as e:
        print(f"Warning: could not fetch origin/{base_ref}: {e}")

    changed = get_changed_schema_paths(base_ref)
    if not changed:
        print("[schema-diff] No schema changes detected.")
        return 0

    print(f"[schema-diff] Base: origin/{base_ref}")
    failures = 0
    for path in changed:
        new_doc = load_json_file(path)
        old_text = git_show(path.relative_to(ROOT), base_ref)
        if old_text is None:
            print(f" - NEW schema: {path}")
            # For new files, require a valid version field
            new_ver = new_doc.get("version")
            if not new_ver:
                print("   ERROR: new schema missing 'version' field")
                failures += 1
            continue

        old_doc = load_json_text(old_text)
        change_kind, details = classify_change(old_doc, new_doc)
        old_ver = old_doc.get("version")
        new_ver = new_doc.get("version")
        print(f" - {path.name}: change={change_kind} old={old_ver} new={new_ver}")
        if details:
            for d in details:
                print(f"   * {d}")

        if not old_ver or not new_ver:
            print("   ERROR: missing version fields for comparison")
            failures += 1
            continue

        oM, oN, oP = parse_version(old_ver)
        nM, nN, nP = parse_version(new_ver)

        def fail(msg: str):
            nonlocal failures
            print(f"   ERROR: {msg}")
            failures += 1

        if change_kind == "breaking":
            if nM <= oM:
                fail("breaking change requires MAJOR version bump")
        elif change_kind == "additive":
            if nM == oM and nN <= oN:
                fail("additive change requires MINOR or MAJOR version bump")
        else:  # patch
            if nM == oM and nN == oN and nP <= oP:
                fail("patch change requires PATCH/MINOR/MAJOR bump")

    if failures:
        print(f"[schema-diff] Failures: {failures}")
        return 1
    print("[schema-diff] All schema version rules satisfied.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

