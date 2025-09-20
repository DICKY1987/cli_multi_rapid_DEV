#!/usr/bin/env python3
"""
Deterministic edit applier for AI Edit Plans.
Safe path handling, checksum verification, and bottom-up range application.

Notes:
- Accepts either a plan object with `edits` or a raw list of edits.
- For insert/append/prepend/create_file, supports `content` (preferred) or `new_content` (alias).
- Insert supports line_number==0 as beginning of file; otherwise 1-indexed.
"""
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple


def _norm_sep(s: str) -> str:
    return s.replace("\\", "/")


def _safe_path(raw: str) -> Path:
    raw_s = raw or ""
    if Path(raw_s).is_absolute() or raw_s.startswith("/"):
        raise ValueError(f"Unsafe absolute path: {raw_s}")
    if re.match(r"^[A-Za-z]:[\\/]", raw_s):
        raise ValueError(f"Unsafe drive-qualified path: {raw_s}")
    parts = _norm_sep(raw_s).split("/")
    if ".." in parts:
        raise ValueError(f"Path traversal not allowed: {raw_s}")
    return Path(raw_s)


def _sha256_bytes(b: bytes) -> str:
    import hashlib

    return hashlib.sha256(b).hexdigest()


def _split_lines(text: str) -> List[str]:
    return text.splitlines(keepends=True)


def _apply_to_file(
    file_path: Path, edits: List[Dict[str, Any]], checksum_expected: str | None = None
) -> Tuple[int, int]:
    created = 0
    modified = 0
    exists = file_path.exists()

    if checksum_expected and exists:
        actual = _sha256_bytes(file_path.read_bytes())
        if actual.lower() != checksum_expected.lower():
            raise RuntimeError(f"Checksum mismatch for {file_path}")

    creates = [e for e in edits if e.get("edit_type") == "create_file"]
    non_creates = [e for e in edits if e.get("edit_type") != "create_file"]

    if creates:
        if exists:
            raise RuntimeError(f"{file_path} already exists; create_file not allowed")
        content = ""
        for e in creates:
            c = e.get("content") or e.get("new_content") or ""
            if c:
                content = c
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(content, encoding="utf-8")
        exists = True
        created += 1

    if non_creates:
        if not exists:
            raise RuntimeError(f"{file_path} not found for non-create edits")
        lines = _split_lines(file_path.read_text(encoding="utf-8"))

        ranges = []
        for e in non_creates:
            et = e.get("edit_type")
            if et in ("replace", "delete"):
                s = int(e["start_line"]) - 1
                e_ = int(e["end_line"]) - 1
                ranges.append((s, e_, e))
            elif et == "insert":
                ln = int(e["line_number"])  # 0 means beginning
                idx = 0 if ln == 0 else ln - 1
                ranges.append((idx, idx - 1, e))
            elif et == "append":
                ranges.append((len(lines), len(lines) - 1, e))
            elif et == "prepend":
                ranges.append((0, -1, e))

        ranges.sort(key=lambda t: (t[0], t[1]), reverse=True)

        for s_idx, e_idx, e in ranges:
            et = e.get("edit_type")
            if et in ("replace", "delete"):
                orig = e.get("original_content")
                current = "".join(lines[s_idx : e_idx + 1])
                if orig is not None and current != orig:
                    raise RuntimeError(
                        f"original_content mismatch in {file_path} for lines {s_idx+1}-{e_idx+1}"
                    )
                if et == "replace":
                    newc = e.get("new_content", "")
                    new_lines = _split_lines(newc)
                    lines[s_idx : e_idx + 1] = new_lines
                else:
                    del lines[s_idx : e_idx + 1]
            elif et == "insert":
                payload = e.get("content") or e.get("new_content", "")
                new_lines = _split_lines(payload)
                insert_at = s_idx
                lines[insert_at:insert_at] = new_lines
            elif et == "append":
                payload = e.get("content") or e.get("new_content", "")
                new_lines = _split_lines(payload)
                lines.extend(new_lines)
            elif et == "prepend":
                payload = e.get("content") or e.get("new_content", "")
                new_lines = _split_lines(payload)
                lines[0:0] = new_lines

        file_path.write_text("".join(lines), encoding="utf-8")
        modified += 1

    return created, modified


def _load_obj(path: Path):
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def main():
    if len(sys.argv) != 2:
        print("Usage: python tools/apply_edits.py <plan_or_edits.json>")
        return 1
    obj = _load_obj(Path(sys.argv[1]))
    if isinstance(obj, dict) and "edits" in obj:
        edits = obj["edits"]
        meta = obj.get("metadata", {})
    elif isinstance(obj, list):
        edits = obj
        meta = {}
    else:
        raise ValueError("Input must be list or object with 'edits'.")

    # group by file
    by_file: Dict[str, List[Dict[str, Any]]] = {}
    for e in edits:
        fp = str(e.get("file_path", "")).strip()
        target = _safe_path(fp)
        by_file.setdefault(str(target), []).append(e)

    created_total = 0
    modified_total = 0
    checksums = (meta or {}).get("pre_edit_checksums") or {}
    for rel, e_list in by_file.items():
        created, modified = _apply_to_file(Path(rel), e_list, checksums.get(rel))
        created_total += created
        modified_total += modified

    report = {
        "created_files": created_total,
        "modified_files": modified_total,
        "total_edits": len(edits),
    }
    print(json.dumps({"status": "ok", "report": report}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
