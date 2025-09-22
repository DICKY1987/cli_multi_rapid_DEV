#!/usr/bin/env python3
import argparse
import hashlib
import json
from pathlib import Path


def load_json(p: Path):
    return json.loads(p.read_text(encoding="utf-8-sig"))


def sha256_hex(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def validate_deliverables(manifest_path: Path) -> dict:
    manifest = load_json(manifest_path)
    results = []
    for d in manifest.get("deliverables", []):
        res = {
            "id": d.get("id"),
            "type": d.get("type"),
            "path": d.get("path"),
            "status": "ok",
            "errors": [],
        }
        if d.get("type") == "file":
            p = Path(d.get("path", ""))
            if d.get("must_exist", True) and not p.exists():
                res["status"] = "fail"
                res["errors"].append("file_missing")
            else:
                try:
                    data = p.read_bytes()
                    if (
                        d.get("expected_sha256")
                        and sha256_hex(data) != d["expected_sha256"]
                    ):
                        res["status"] = "fail"
                        res["errors"].append("checksum_mismatch")
                    text = None
                    if d.get("must_contain"):
                        try:
                            text = data.decode("utf-8")
                        except Exception:
                            res["status"] = "fail"
                            res["errors"].append("decode_failed")
                        if text is not None:
                            for token in d["must_contain"]:
                                if token not in text:
                                    res["status"] = "fail"
                                    res["errors"].append(f"missing_token:{token}")
                except Exception as e:
                    res["status"] = "fail"
                    res["errors"].append(f"read_error:{e}")
        results.append(res)
    summary = {
        "total": len(results),
        "failures": sum(1 for r in results if r["status"] != "ok"),
    }
    return {"results": results, "summary": summary}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", required=True)
    args = ap.parse_args()
    report = validate_deliverables(Path(args.manifest))
    out = Path(args.manifest).with_name("deliverables.validation.json")
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"Validation report: {out}")


if __name__ == "__main__":
    main()
