#!/usr/bin/env python3
import argparse
import base64
import hashlib
import json
import re
from pathlib import Path
from typing import Dict, List

SRC_FILES = [
    "codex_arch_spec.json",
    "claude_github_integration_spec.json",
    "source_specs/codex_arch_spec.json",
    "source_specs/claude_github_integration_spec.json",
]

RE_CLAUDE = re.compile(
    r'"op"\s*:\s*"create_file"\s*,\s*"path"\s*:\s*"([^"]+)"\s*,\s*"content_base64"\s*:\s*"([^"]+)"',
    re.DOTALL,
)
RE_CODEX = re.compile(
    r'"operation"\s*:\s*"create"\s*,\s*"path"\s*:\s*"([^"]+)"\s*,\s*"content"\s*:\s*(\{[\s\S]*?\})\s*(?:\}|,|\])',
    re.DOTALL,
)


def sha256_hex(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def to_b64_json(obj) -> str:
    data = json.dumps(obj, separators=(",", ":")).encode("utf-8")
    return base64.b64encode(data).decode("utf-8")


def extract_ops_from_text(text: str) -> List[Dict]:
    ops = []
    for m in RE_CLAUDE.finditer(text):
        path, b64 = m.group(1), m.group(2)
        ops.append(
            {
                "op": "write_file",
                "path": path,
                "content_base64": b64,
                "if_exists": "skip",
            }
        )
    for m in RE_CODEX.finditer(text):
        path, cjson = m.group(1), m.group(2)
        try:
            obj = json.loads(cjson)
        except Exception:
            continue
        ops.append(
            {
                "op": "write_file",
                "path": path,
                "content_base64": to_b64_json(obj),
                "if_exists": "skip",
            }
        )
    return ops


def load_or_repair(src: Path) -> Dict:
    try:
        obj = json.loads(src.read_text(encoding="utf-8"))
        return obj
    except Exception:
        ops = extract_ops_from_text(src.read_text(encoding="utf-8", errors="ignore"))
        return {"metadata": {"source": src.name}, "ops": ops}


def merge_into_plan(plan_path: Path, extracted_ops: List[Dict]) -> None:
    plan = json.loads(plan_path.read_text(encoding="utf-8-sig"))
    existing = set(
        op["path"] for op in plan.get("ops", []) if op.get("op") == "write_file"
    )
    for op in extracted_ops:
        if op["path"] in existing:
            continue
        # augment
        data = base64.b64decode(op["content_base64"])
        op["checksum_sha256"] = sha256_hex(data)
        op["phase"] = "apply"
        op["dry_run_effect"] = "noop"
        plan["ops"].append(op)
        existing.add(op["path"])
    plan_path.write_text(json.dumps(plan, indent=2), encoding="utf-8")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=".")
    ap.add_argument("--plan", default="combined_repo_plan.json")
    args = ap.parse_args()

    root = Path(args.root)
    plan_path = root / args.plan
    if not plan_path.exists():
        raise SystemExit(f"Plan not found: {plan_path}")

    all_ops = []
    for name in SRC_FILES:
        src = root / name
        if not src.exists():
            continue
        obj = load_or_repair(src)
        # Write repaired copy for visibility
        repaired = root / (src.stem + ".repaired.json")
        repaired.write_text(json.dumps(obj, indent=2), encoding="utf-8")
        # Normalize to ops list
        ops = []
        if "file_operations" in obj:
            for it in obj["file_operations"]:
                if it.get("operation") == "create":
                    ops.append(
                        {
                            "op": "write_file",
                            "path": it["path"],
                            "content_base64": to_b64_json(it["content"]),
                            "if_exists": "skip",
                        }
                    )
        if "operations" in obj:
            for it in obj["operations"]:
                if it.get("op") == "create_file":
                    ops.append(
                        {
                            "op": "write_file",
                            "path": it["path"],
                            "content_base64": it["content_base64"],
                            "if_exists": "skip",
                        }
                    )
        if "ops" in obj:
            for it in obj["ops"]:
                if it.get("op") == "write_file":
                    ops.append(it)
        if not ops:
            ops = extract_ops_from_text(
                src.read_text(encoding="utf-8", errors="ignore")
            )
        all_ops.extend(ops)

    # Deduplicate by (path, checksum) to keep first
    dedup = {}
    for op in all_ops:
        key = (op["path"], op.get("content_base64"))
        if key not in dedup:
            dedup[key] = op

    merge_into_plan(plan_path, list(dedup.values()))
    print("Repaired files written and plan merged successfully.")


if __name__ == "__main__":
    main()
