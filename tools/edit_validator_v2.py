#!/usr/bin/env python3
"""
Edit Plan/Batch Validator v2
- Accepts either a list[edit] or an object {"edits":[...], "metadata":{...}}
- Hardens path safety (no absolute paths, no drive letters, no '..')
- Adjusts conflict detection to allow adjacency (no error when ranges touch)
- Optionally verifies per-edit or plan-level pre_edit_checksum (if present)
"""
import json
import re
from pathlib import Path
from typing import List, Dict, Any, Tuple
from datetime import datetime
import hashlib

try:
    import jsonschema
except Exception:
    jsonschema = None


class EditValidatorV2:
    def __init__(self, schema_path: str = ".ai/schemas/edit_schema.json", plan_schema_path: str = ".ai/schemas/plan.schema.json"):
        self.schema_path = schema_path
        self.plan_schema_path = plan_schema_path
        self._edit_schema = None
        self._plan_schema = None
        if jsonschema is not None:
            with open(self.schema_path, "r", encoding="utf-8-sig") as f:
                self._edit_schema = json.load(f)
            try:
                with open(self.plan_schema_path, "r", encoding="utf-8-sig") as f:
                    self._plan_schema = json.load(f)
            except FileNotFoundError:
                self._plan_schema = None
            # Inline item schema to avoid $ref resolution issues
            if self._plan_schema and "properties" in self._plan_schema and "edits" in self._plan_schema["properties"]:
                try:
                    if isinstance(self._plan_schema["properties"]["edits"].get("items"), dict) and "$ref" in self._plan_schema["properties"]["edits"]["items"]:
                    self._plan_schema["properties"]["edits"]["items"] = self._edit_schema
                except Exception:
                    pass

    def load_edits(self, obj: Any) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        if isinstance(obj, list):
            return obj, {}
        if isinstance(obj, dict) and "edits" in obj and isinstance(obj["edits"], list):
            return obj["edits"], obj.get("metadata", {}) or {}
        raise ValueError("Input must be a list of edits or an object with an 'edits' array.")

    def validate_against_schema(self, obj: Any) -> Tuple[bool, List[str]]:
        if jsonschema is None:
            return True, []
        errors = []
        if self._plan_schema and isinstance(obj, dict):
            validator = jsonschema.Draft202012Validator(self._plan_schema)
            for err in sorted(validator.iter_errors(obj), key=lambda e: e.path):
                errors.append(self._format_schema_error(err))
            return len(errors) == 0, errors
        else:
            validator = jsonschema.Draft202012Validator(self._edit_schema)
            if isinstance(obj, list):
                for i, edit in enumerate(obj):
                    for err in sorted(validator.iter_errors(edit), key=lambda e: e.path):
                        errors.append(f"[{i}] " + self._format_schema_error(err))
                return len(errors) == 0, errors
            elif isinstance(obj, dict) and "edits" in obj:
                for i, edit in enumerate(obj["edits"]):
                    for err in sorted(validator.iter_errors(edit), key=lambda e: e.path):
                        errors.append(f"[edits[{i}]] " + self._format_schema_error(err))
                return len(errors) == 0, errors
            else:
                return False, ["Input was neither a list nor a plan object"]

    def validate_business_rules(self, edits: List[Dict[str, Any]], metadata: Dict[str, Any]) -> List[str]:
        errors = []
        errors += self._validate_file_safety(edits)
        errors += self._validate_line_consistency(edits)
        errors += self._validate_edit_conflicts(edits)
        errors += self._validate_content_integrity(edits)
        errors += self._validate_pre_edit_checksums(edits, metadata)
        return errors

    def generate_report(self, obj: Any) -> Dict[str, Any]:
        edits, metadata = self.load_edits(obj)
        schema_ok, schema_errors = self.validate_against_schema(obj)
        business_errors = self.validate_business_rules(edits, metadata)

        is_valid = schema_ok and (len(business_errors) == 0)
        all_errors = []
        if not schema_ok:
            all_errors += [f"SCHEMA: {e}" for e in schema_errors]
        all_errors += [f"RULE: {e}" for e in business_errors]

        file_stats = self._build_file_stats(edits)

        return {
            "validation": {"is_valid": is_valid, "error_count": len(all_errors), "errors": all_errors},
            "summary": {
                "total_edits": len(edits),
                "files_affected": len(file_stats),
                "edit_types": sorted(list(set(edit.get("edit_type") for edit in edits))),
                "file_stats": file_stats,
            },
            "signatures": [self.create_edit_signature(edit) for edit in edits],
            "validated_at": datetime.utcnow().isoformat() + "Z",
        }

    def _validate_file_safety(self, edits: List[Dict[str, Any]]) -> List[str]:
        errors = []
        for edit in edits:
            raw = str(edit.get("file_path", ""))
            p = Path(raw)
            if p.is_absolute() or raw.startswith("/"):
                errors.append(f"Absolute paths not allowed: {raw}")
            if re.match(r"^[A-Za-z]:[\\/]", raw):
                errors.append(f"Drive-qualified path not allowed: {raw}")
            parts = raw.replace("\\", "/").split("/")
            if ".." in parts:
                errors.append(f"Path traversal not allowed: {raw}")
        return errors

    def _validate_line_consistency(self, edits: List[Dict[str, Any]]) -> List[str]:
        errors = []
        for i, edit in enumerate(edits):
            et = edit.get("edit_type")
            if et in ("replace", "delete"):
                s, e = edit.get("start_line"), edit.get("end_line")
                if not isinstance(s, int) or not isinstance(e, int) or s < 1 or e < s:
                    errors.append(f"[{i}] invalid start/end_line: {s}, {e}")
            elif et == "insert":
                line = edit.get("line_number")
                if not isinstance(line, int) or line < 0:
                    errors.append(f"[{i}] invalid line_number: {line}")
        return errors

    def _validate_edit_conflicts(self, edits: List[Dict[str, Any]]) -> List[str]:
        errors = []
        by_file: Dict[str, List[Tuple[int, int, int, str]]] = {}
        for idx, edit in enumerate(edits):
            f = edit.get("file_path")
            et = edit.get("edit_type")
            if et in ("replace", "delete"):
                s, e = edit.get("start_line", 0), edit.get("end_line", 0)
            elif et == "insert":
                ln = edit.get("line_number", 0)
                s = e = 0 if ln == 0 else ln
            else:
                continue
            by_file.setdefault(f, []).append((s, e, idx, et))

        for f, ranges in by_file.items():
            ranges.sort()
            for (cs, ce, ci, ct), (ns, ne, ni, nt) in zip(ranges, ranges[1:]):
                if ce > ns:
                    errors.append(
                        f"Conflicting edits on {f}: [{ci}:{ct} {cs}-{ce}] overlaps [{ni}:{nt} {ns}-{ne}]"
                    )
        return errors

    def _validate_content_integrity(self, edits: List[Dict[str, Any]]) -> List[str]:
        errors = []
        for i, edit in enumerate(edits):
            et = edit.get("edit_type")
            if et in ("replace", "delete"):
                if not edit.get("original_content"):
                    errors.append(f"[{i}] original_content is required for replace/delete")
            for key in ("new_content", "content"):
                if key in edit and isinstance(edit[key], str):
                    if any(len(line) > 12000 for line in edit[key].splitlines()):
                        errors.append(f"[{i}] {key} contains an unusually long line (>12k chars)")
        return errors

    def _validate_pre_edit_checksums(self, edits: List[Dict[str, Any]], metadata: Dict[str, Any]) -> List[str]:
        errors = []
        checksum_map = metadata.get("pre_edit_checksums") or {}
        for i, e in enumerate(edits):
            expected = e.get("pre_edit_checksum") or checksum_map.get(e.get("file_path"))
            if expected:
                path = Path(e.get("file_path"))
                if not path.exists():
                    errors.append(f"[{i}] checksum provided but file missing: {path}")
                    continue
                data = path.read_bytes()
                actual = hashlib.sha256(data).hexdigest()
                if actual.lower() != str(expected).lower():
                    errors.append(f"[{i}] pre_edit_checksum mismatch for {path}")
        return errors

    def create_edit_signature(self, edit: Dict[str, Any]) -> str:
        m = hashlib.sha256()
        payload = "|".join(str(edit.get(k, "")) for k in ("edit_id", "file_path", "edit_type", "created_at"))
        m.update(payload.encode("utf-8"))
        return m.hexdigest()

    def _build_file_stats(self, edits: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
        stats: Dict[str, Dict[str, Any]] = {}
        for e in edits:
            f = e.get("file_path", "")
            stats.setdefault(f, {"count": 0, "types": set()})
            stats[f]["count"] += 1
            stats[f]["types"].add(e.get("edit_type"))
        for s in stats.values():
            s["types"] = sorted(list(s["types"]))
        return stats

    def _format_schema_error(self, err) -> str:
        loc = "$" + "".join(f"[{repr(p)}]" if isinstance(p, int) else f".{p}" for p in err.absolute_path)
        return f"{loc}: {err.message}"


def _load_json(path: str):
    with open(path, "r", encoding="utf-8-sig") as f:
        return json.load(f)


if __name__ == "__main__":
    import sys

    if len(sys.argv) != 2:
        print("Usage: python tools/edit_validator_v2.py <plan_or_edits.json>")
        sys.exit(1)
    obj = _load_json(sys.argv[1])
    v = EditValidatorV2()
    report = v.generate_report(obj)
    print(json.dumps(report))
    sys.exit(0 if report["validation"]["is_valid"] else 2)



