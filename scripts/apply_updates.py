#!/usr/bin/env python3
import argparse
import base64
import json
import re
import sys
from pathlib import Path

try:
    import jsonschema  # type: ignore
except Exception:
    jsonschema = None

MODULES_DIR = Path(".ai/plan_modules")

OP_TYPES = {
    "write_file",
    "replace_section",
    "assert_contains",
    "assert_not_contains",
    "locate",
}


def load_json(p: Path):
    return json.loads(p.read_text(encoding="utf-8-sig"))


def dump_json(p: Path, obj):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj, indent=2), encoding="utf-8")


def validate_update(update: dict, schema_path: Path):
    if jsonschema is None:
        print("[warn] jsonschema not installed; skipping update schema validation")
        return
    schema = load_json(schema_path)
    jsonschema.validate(update, schema)


def normalize_ops(ops, source_name: str):
    out = []
    for op in ops:
        if "op" not in op and "type" in op:
            op = {**op, "op": op["type"]}
        if op.get("op") == "write_file":
            op.setdefault("if_exists", "skip")
            op.setdefault("phase", "apply")
            op.setdefault("dry_run_effect", "noop")
            if "checksum_sha256" not in op and "content_base64" in op:
                import base64 as b64
                import hashlib

                data = b64.b64decode(op["content_base64"])
                op["checksum_sha256"] = hashlib.sha256(data).hexdigest()
            op.setdefault("source", source_name)
        elif op.get("op") == "replace_section":
            op.setdefault("allow_multiple_matches", False)
            op.setdefault("on_duplicate", "skip")
            op.setdefault("phase", "apply")
            op.setdefault("dry_run_effect", "scan_only")
        elif op.get("op") in ("locate", "assert_contains", "assert_not_contains"):
            op.setdefault("phase", "validate")
        out.append(op)
    return out


def load_module_file(name: str):
    p = MODULES_DIR / name
    if not p.exists():
        return {"module": {"name": name}, "ops": []}
    return load_json(p)


def save_module_file(name: str, module_obj: dict):
    dump_json(MODULES_DIR / name, module_obj)


def match_selector(op: dict, sel: dict) -> bool:
    kind = sel.get("kind")
    if kind == "write_file_path" and op.get("op") == "write_file":
        return op.get("path") == sel.get("path")
    if kind == "file" and op.get("file"):
        return op.get("file") == sel.get("file")
    if kind == "op_type":
        return op.get("op") == sel.get("op")
    if kind == "regex":
        field = sel.get("field")
        pattern = sel.get("pattern")
        val = op.get(field, "")
        try:
            return re.search(pattern, str(val)) is not None
        except Exception:
            return False
    return False


def remove_ops(
    module_name: str, selector: dict, max_remove: int | None, required: bool
) -> int:
    mod = load_module_file(module_name)
    ops = mod.get("ops", [])
    kept = []
    removed = 0
    for op in ops:
        if match_selector(op, selector):
            if max_remove is not None and removed >= max_remove:
                kept.append(op)
                continue
            removed += 1
        else:
            kept.append(op)
    if removed == 0 and required:
        raise SystemExit(f"No ops matched selector in module {module_name}")
    mod["ops"] = kept
    save_module_file(module_name, mod)
    return removed


def replace_ops(module_name: str, selector: dict, with_ops: list):
    mod = load_module_file(module_name)
    ops = mod.get("ops", [])
    result = []
    replaced_any = False
    for op in ops:
        if match_selector(op, selector):
            result.extend(with_ops)
            replaced_any = True
        else:
            result.append(op)
    if not replaced_any:
        raise SystemExit(f"No ops matched for replacement in module {module_name}")
    mod["ops"] = result
    save_module_file(module_name, mod)


def upsert_ops(module_name: str, ops: list, strategy: str):
    mod = load_module_file(module_name)
    mod_ops = mod.get("ops", [])
    if strategy == "prepend":
        mod["ops"] = ops + mod_ops
    else:
        mod["ops"] = mod_ops + ops
    save_module_file(module_name, mod)


def add_module(
    filename: str,
    module_meta: dict | None,
    ops: list,
    position: str,
    relative_to: str | None,
):
    # Write module file
    mod_obj = {"module": module_meta or {"name": filename}, "ops": ops}
    save_module_file(filename, mod_obj)
    # Update manifest if present
    manifest_path = MODULES_DIR / "manifest.json"
    if manifest_path.exists():
        mf = load_json(manifest_path)
        if filename not in mf:
            if position == "end" or not relative_to or relative_to not in mf:
                mf.append(filename)
            else:
                idx = mf.index(relative_to)
                if position == "before":
                    mf.insert(idx, filename)
                else:  # after
                    mf.insert(idx + 1, filename)
        dump_json(manifest_path, mf)


def apply_update(update_path: Path, schema_path: Path | None):
    upd = load_json(update_path)
    if schema_path is not None and schema_path.exists():
        try:
            validate_update(upd, schema_path)
        except Exception as e:
            print(f"[error] Update schema validation failed: {e}")
            sys.exit(1)

    for op in upd.get("operations", []):
        t = op.get("type")
        if t == "add_module":
            ops = normalize_ops(op.get("ops", []), update_path.name)
            add_module(
                op["filename"],
                op.get("module"),
                ops,
                op.get("position", "end"),
                op.get("relative_to"),
            )
            print(f"[add_module] {op['filename']} ({len(ops)} ops)")
        elif t == "upsert_ops":
            ops = normalize_ops(op.get("ops", []), update_path.name)
            upsert_ops(op["module"], ops, op.get("strategy", "append"))
            print(f"[upsert_ops] {op['module']} (+{len(ops)} ops)")
        elif t == "remove_ops":
            n = remove_ops(
                op["module"],
                op["selector"],
                op.get("max_remove"),
                op.get("required", True),
            )
            print(f"[remove_ops] {op['module']} (-{n} ops)")
        elif t == "replace_ops":
            ops = normalize_ops(op.get("with_ops", []), update_path.name)
            replace_ops(op["module"], op["selector"], ops)
            print(f"[replace_ops] {op['module']} (replaced with {len(ops)} ops)")
        elif t == "set_metadata":
            meta_p = Path("metadata.json")
            meta = {} if not meta_p.exists() else load_json(meta_p)
            meta.update(op.get("patch", {}))
            dump_json(meta_p, meta)
            print("[set_metadata] updated")
        elif t == "set_defaults":
            df_p = Path("defaults.json")
            df = {} if not df_p.exists() else load_json(df_p)
            df.update(op.get("patch", {}))
            dump_json(df_p, df)
            print("[set_defaults] updated")
        elif t == "set_execution":
            ex_p = Path("execution.json")
            ex = {} if not ex_p.exists() else load_json(ex_p)
            ex.update(op.get("patch", {}))
            dump_json(ex_p, ex)
            print("[set_execution] updated")
        elif t == "set_paths":
            # Paths live in final plan; store as special module for composer to pick or maintain in defaults
            pf = Path("paths.json")
            dump_json(
                pf,
                {
                    "paths_allowlist": op.get("allow", []),
                    "paths_denylist": op.get("deny", []),
                },
            )
            print("[set_paths] updated")
        elif t == "update_manifest":
            mf_p = MODULES_DIR / "manifest.json"
            dump_json(mf_p, op.get("manifest", []))
            print("[update_manifest] updated manifest")
        else:
            print(f"[warn] unknown update operation: {t}")


def write_deliverables_manifest(update: dict):
    import hashlib
    import json
    import re
    from pathlib import Path

    raw_id = update.get("update_id", "unknown") or "unknown"
    safe_id = re.sub(r"[^A-Za-z0-9._-]+", "-", raw_id)
    outdir = Path("artifacts") / "updates" / safe_id
    outdir.mkdir(parents=True, exist_ok=True)
    deliverables = update.get("deliverables", [])
    # collect write_file ops in this update for checksum inference
    created = {}
    for op in update.get("operations", []):
        if op.get("type") in ("add_module", "upsert_ops", "replace_ops"):
            ops = op.get("ops") or op.get("with_ops") or []
            for w in ops:
                if (
                    (w.get("op") or w.get("type")) == "write_file"
                    and w.get("path")
                    and w.get("content_base64")
                ):
                    data = base64.b64decode(w["content_base64"])
                    created[w["path"]] = hashlib.sha256(data).hexdigest()
    for d in deliverables:
        if (
            d.get("type") == "file"
            and not d.get("expected_sha256")
            and d.get("path") in created
        ):
            d["expected_sha256"] = created[d["path"]]
    manifest = {
        "update_id": update.get("update_id"),
        "version": update.get("version"),
        "target_repo": update.get("target_repo"),
        "deliverables": deliverables,
    }
    (outdir / "deliverables.manifest.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )
    print(f"[deliverables] manifest written: {outdir / 'deliverables.manifest.json'}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--update", required=True, help="Path to update JSON file")
    ap.add_argument(
        "--schema", default=str(Path(".ai/schemas/plan_update.schema.json"))
    )
    args = ap.parse_args()

    update_path = Path(args.update)
    schema_path = Path(args.schema)
    apply_update(update_path, schema_path)
    upd = load_json(update_path)
    write_deliverables_manifest(upd)
    print("Update applied to modules. You can now compose the plan.")


if __name__ == "__main__":
    main()
