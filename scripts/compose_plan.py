#!/usr/bin/env python3
import argparse
import base64
import glob
import hashlib
import json
from pathlib import Path


def sha256_hex(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def load_json(p: Path, optional=False):
    if not p.exists():
        if optional:
            return None
        raise SystemExit(f"missing: {p}")
    return json.loads(p.read_text(encoding="utf-8-sig"))


DEF_ORDER_FILES = [
    "10-validate.json",
    "20-replace_sections.json",
    "30-files-schemas.json",
    "31-files-samples.json",
    "40-files-docs.json",
    "50-files-other.json",
]


def ensure_writefile_defaults(op: dict, src: str):
    if op.get("op") != "write_file":
        return
    if "if_exists" not in op:
        op["if_exists"] = "skip"
    if "phase" not in op:
        op["phase"] = "apply"
    if "dry_run_effect" not in op:
        op["dry_run_effect"] = "noop"
    if "checksum_sha256" not in op and "content_base64" in op:
        data = base64.b64decode(op["content_base64"])
        op["checksum_sha256"] = sha256_hex(data)
    if "source" not in op:
        op["source"] = src


def ensure_replace_defaults(op: dict, src: str):
    if op.get("op") != "replace_section":
        return
    op.setdefault("allow_multiple_matches", False)
    op.setdefault("on_duplicate", "skip")
    op.setdefault("phase", "apply")
    op.setdefault("dry_run_effect", "scan_only")


def ensure_validate_defaults(op: dict, src: str):
    if op.get("op") in ("locate", "assert_contains", "assert_not_contains"):
        op.setdefault("phase", "validate")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--modules", default=".ai/plan_modules")
    ap.add_argument("--metadata", default="metadata.json")
    ap.add_argument("--defaults", default="defaults.json")
    ap.add_argument("--execution", default="execution.json")
    ap.add_argument("--paths", default="paths.json")
    ap.add_argument("--manifest", default=".ai/plan_modules/manifest.json")
    ap.add_argument("--out", default="combined_repo_plan.json")
    ap.add_argument("--emit-plan-summary", action="store_true")
    args = ap.parse_args()

    root = Path(".")
    modules_dir = root / args.modules

    base = {
        "spec_version": "1.0",
        "metadata": {
            "name": "combined_repo_plan",
            "description": "Composed plan from modules",
        },
        "defaults": {},
        "execution": {"dry_run": True, "phases": ["validate", "apply"]},
        "ops": [],
    }

    md = Path(args.metadata)
    if md.exists():
        base["metadata"].update(load_json(md))
    df = Path(args.defaults)
    if df.exists():
        base["defaults"] = load_json(df)
    ex = Path(args.execution)
    if ex.exists():
        base["execution"] = load_json(ex)

    # Determine module order
    manifest = Path(args.manifest)
    if manifest.exists():
        order = load_json(manifest)
        if not isinstance(order, list):
            raise SystemExit("manifest.json must be a list of filenames")
    else:
        # fallback to default ordering; append any extra modules lexicographically
        existing = set(DEF_ORDER_FILES)
        extra = sorted(
            [
                p.name
                for p in modules_dir.glob("*.json")
                if p.name not in existing and p.name != "manifest.json"
            ]
        )
        order = DEF_ORDER_FILES + extra

    # Merge optional paths allow/deny list
    paths_cfg = Path(args.paths)
    if paths_cfg.exists():
        pjson = load_json(paths_cfg)
        if isinstance(pjson, dict):
            allow = pjson.get("paths_allowlist") or []
            deny = pjson.get("paths_denylist") or []
            if allow:
                base["paths_allowlist"] = allow
            if deny:
                base["paths_denylist"] = deny

    seen_paths = set()

    for name in order:
        p = modules_dir / name
        if not p.exists():
            continue
        mod = load_json(p)
        ops = mod.get("ops", [])
        src = name
        for op in ops:
            # Normalize and enrich
            ensure_writefile_defaults(op, src)
            ensure_replace_defaults(op, src)
            ensure_validate_defaults(op, src)
            # De-dupe write_file by path
            if op.get("op") == "write_file":
                path = op.get("path")
                if path in seen_paths:
                    continue
                seen_paths.add(path)
            base["ops"].append(op)

    # Compute optional fingerprint
    ops_json = json.dumps(base["ops"], separators=(",", ":"), sort_keys=True).encode(
        "utf-8"
    )
    base["plan_fingerprint"] = {"method": "sha256_ops", "value": sha256_hex(ops_json)}

    if "$schema" not in base:
        base["$schema"] = ".ai/schemas/combined_plan.schema.json"

    # Aggregate deliverables manifests (if any) into metadata summary
    try:
        upd_manifests = sorted(
            glob.glob(
                str(Path("artifacts") / "updates" / "*" / "deliverables.manifest.json")
            )
        )
        if upd_manifests:
            summaries = []
            for mf in upd_manifests:
                try:
                    m = load_json(Path(mf))
                    summaries.append(
                        {
                            "update_id": m.get("update_id"),
                            "version": m.get("version"),
                            "deliverables": m.get("deliverables", []),
                        }
                    )
                except Exception:
                    continue
            base.setdefault("metadata", {}).update(
                {"deliverables_summary": summaries[-5:]}
            )
    except Exception:
        pass

    Path(args.out).write_text(json.dumps(base, indent=2), encoding="utf-8")
    print(f"Composed plan written: {args.out}")

    # Optionally emit a plan summary artifact with fingerprint and deliverables
    if args.emit_plan_summary:
        summary_dir = Path("artifacts") / "plan"
        summary_dir.mkdir(parents=True, exist_ok=True)
        summary = {
            "out": args.out,
            "fingerprint": base["plan_fingerprint"],
            "deliverables_summary": base.get("metadata", {}).get(
                "deliverables_summary", []
            ),
        }
        (summary_dir / "plan.summary.json").write_text(
            json.dumps(summary, indent=2), encoding="utf-8"
        )
        print(f"Plan summary written: {summary_dir / 'plan.summary.json'}")


if __name__ == "__main__":
    main()
