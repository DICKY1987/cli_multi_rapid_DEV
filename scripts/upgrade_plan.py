#!/usr/bin/env python3
import argparse
import base64
import hashlib
import json
from pathlib import Path

try:
    import jsonschema  # type: ignore
except Exception:
    jsonschema = None


def sha256_hex(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def load_json(p: Path) -> dict:
    return json.loads(p.read_text(encoding="utf-8-sig"))


def save_json(p: Path, obj: dict) -> None:
    p.write_text(json.dumps(obj, indent=2), encoding="utf-8")


def normalize_op(op: dict, source: str = "upgrade") -> dict:
    t = op.get("op") or op.get("type")
    if not t:
        return op
    op["op"] = t
    if t == "write_file":
        op.setdefault("if_exists", "skip")
        op.setdefault("phase", "apply")
        op.setdefault("dry_run_effect", "noop")
        if "checksum_sha256" not in op and "content_base64" in op:
            try:
                data = base64.b64decode(op["content_base64"])
                op["checksum_sha256"] = sha256_hex(data)
            except Exception:
                pass
        op.setdefault("source", source)
    elif t == "replace_section":
        op.setdefault("allow_multiple_matches", False)
        op.setdefault("on_duplicate", "skip")
        op.setdefault("phase", "apply")
        op.setdefault("dry_run_effect", "scan_only")
    elif t in ("locate", "assert_contains", "assert_not_contains"):
        op.setdefault("phase", "validate")
    return op


def upgrade_plan(plan: dict, schema_path: Path | None) -> dict:
    # Move alternate operation keys to 'ops'
    ops = []
    if "ops" in plan and isinstance(plan["ops"], list):
        ops.extend(plan["ops"])
    if "operations" in plan and isinstance(plan["operations"], list):
        # if these are already normalized, just extend; otherwise map
        for it in plan["operations"]:
            kind = it.get("op")
            if kind:
                ops.append(it)
    if "file_operations" in plan and isinstance(plan["file_operations"], list):
        for it in plan["file_operations"]:
            if it.get("operation") == "create":
                content = it.get("content")
                if content is None:
                    continue
                try:
                    data = json.dumps(content, separators=(",", ":")).encode("utf-8")
                    b64 = base64.b64encode(data).decode("utf-8")
                    ops.append(
                        {
                            "op": "write_file",
                            "path": it.get("path"),
                            "content_base64": b64,
                            "if_exists": "skip",
                        }
                    )
                except Exception:
                    continue

    # Normalize
    norm_ops = []
    seen_paths = set()
    for o in ops:
        o = normalize_op(o)
        if o.get("op") == "write_file":
            p = o.get("path")
            if p in seen_paths:
                continue
            seen_paths.add(p)
        norm_ops.append(o)

    plan["ops"] = norm_ops
    # Remove legacy keys if present
    for k in ("operations", "file_operations"):
        if k in plan:
            del plan[k]

    # Ensure top-level fields
    plan.setdefault("spec_version", "1.0")
    plan.setdefault("metadata", {})
    plan.setdefault("defaults", {})
    plan.setdefault("execution", {"dry_run": True, "phases": ["validate", "apply"]})
    plan.setdefault("$schema", ".ai/schemas/combined_plan.schema.json")

    # Fingerprint
    ops_json = json.dumps(plan["ops"], separators=(",", ":"), sort_keys=True).encode(
        "utf-8"
    )
    plan["plan_fingerprint"] = {"method": "sha256_ops", "value": sha256_hex(ops_json)}

    # Optionally validate against schema
    if schema_path and jsonschema is not None and schema_path.exists():
        schema = load_json(schema_path)
        jsonschema.validate(plan, schema)

    return plan


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="in_path", required=True)
    ap.add_argument("--out", dest="out_path", required=True)
    ap.add_argument(
        "--schema", default=str(Path(".ai/schemas/combined_plan.schema.json"))
    )
    args = ap.parse_args()

    in_p = Path(args.in_path)
    out_p = Path(args.out_path)
    schema_p = Path(args.schema)

    plan = load_json(in_p)
    plan_up = upgrade_plan(plan, schema_p)
    save_json(out_p, plan_up)
    print(f"Upgraded plan written: {out_p}")


if __name__ == "__main__":
    main()
