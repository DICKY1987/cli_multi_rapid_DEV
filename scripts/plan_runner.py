#!/usr/bin/env python3
import argparse, base64, hashlib, json, os, re, shutil, sys, tempfile
from glob import glob
from pathlib import Path

try:
    import jsonschema  # type: ignore
except Exception:
    jsonschema = None

class Context:
    def __init__(self):
        self.vars = {}
    def sub(self, s: str) -> str:
        out = s
        for k, v in self.vars.items():
            out = out.replace(f"${k}", v)
        return out

def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def canonicalize_ops(ops) -> str:
    # Canonical JSON of ops for fingerprint verification
    return json.dumps(ops, separators=(',',':'), sort_keys=True)

def load_plan(path: Path) -> dict:
    with path.open('r', encoding='utf-8-sig') as f:
        return json.load(f)

def validate_schema(plan: dict, schema_path: Path) -> None:
    if jsonschema is None:
        print('[warn] jsonschema not installed; skipping schema validation')
        return
    with schema_path.open('r', encoding='utf-8') as f:
        schema = json.load(f)
    jsonschema.validate(plan, schema)

def ensure_allowed(path: Path, allowlist, denylist):
    p = str(path).replace('\\','/')
    if allowlist:
        allowed = any(p.startswith(a.rstrip('/')) for a in allowlist)
        if not allowed:
            raise RuntimeError(f'path not in allowlist: {p}')
    if denylist:
        denied = any(p.startswith(d.rstrip('/')) for d in denylist)
        if denied:
            raise RuntimeError(f'path denied by denylist: {p}')

def normalize_eol_bytes(data: bytes, mode: str, encoding: str) -> bytes:
    if mode == 'preserve':
        return data
    text = data.decode(encoding)
    text = text.replace('\r\n','\n').replace('\r','\n')
    if mode == 'lf':
        return text.encode(encoding)
    if mode == 'crlf':
        return text.replace('\n','\r\n').encode(encoding)
    return data

# Ops

def op_locate(op: dict, ctx: Context) -> None:
    pattern = op['glob']
    must = op.get('must_contain', [])
    matches = []
    for path in glob(pattern, recursive=True):
        try:
            text = Path(path).read_text(encoding='utf-8', errors='ignore')
        except Exception:
            continue
        if all(token in text for token in must):
            matches.append(path)
    if not matches:
        raise RuntimeError(f"locate failed for id={op['id']} pattern={pattern}")
    ctx.vars[op['id']] = matches[0]
    print(f"[locate] {op['id']} -> {matches[0]}")

def op_assert_contains(op: dict, ctx: Context) -> None:
    file_path = Path(ctx.sub(op['file']))
    if not file_path.exists():
        raise RuntimeError(f"assert_contains file not found: {file_path}")
    text = file_path.read_text(encoding='utf-8', errors='ignore')
    for token in op['must_contain']:
        if token not in text:
            raise RuntimeError(f"assert_contains missing token in {file_path}: {token}")
    print(f"[assert] ok: {file_path}")

def op_assert_not_contains(op: dict, ctx: Context) -> None:
    file_path = Path(ctx.sub(op['file']))
    if not file_path.exists():
        raise RuntimeError(f"assert_not_contains file not found: {file_path}")
    text = file_path.read_text(encoding='utf-8', errors='ignore')
    for token in op['must_not_contain']:
        if token in text:
            raise RuntimeError(f"assert_not_contains found forbidden token in {file_path}: {token}")
    print(f"[assert_not] ok: {file_path}")


def op_replace_section(op: dict, ctx: Context, dry_run: bool, shadow_root: Path|None, allowlist, denylist) -> None:
    file_path_real = Path(ctx.sub(op['file']))
    if not file_path_real.exists():
        raise RuntimeError(f"replace_section file not found: {file_path_real}")
    ensure_allowed(file_path_real, allowlist, denylist)
    content = file_path_real.read_text(encoding='utf-8', errors='ignore')
    start_re = re.compile(op['start_regex'], re.DOTALL)
    end_re = re.compile(op['end_regex'], re.DOTALL)

    matches = list(start_re.finditer(content))
    if not matches:
        raise RuntimeError('replace_section start_regex not found')
    if not op.get('allow_multiple_matches', False) and len(matches) > 1:
        raise RuntimeError('replace_section multiple start matches and allow_multiple_matches=false')

    # For simplicity, operate on the first match and corresponding end
    start_m = matches[0]
    end_m = end_re.search(content, start_m.end())
    if not end_m:
        raise RuntimeError('replace_section end_regex not found after start')

    # Optional idempotency check
    idem = op.get('idempotency_marker')
    if idem and idem in content:
        action = op.get('on_duplicate', 'skip')
        if action == 'error':
            raise RuntimeError('idempotency_marker already present')
        elif action == 'skip':
            print('[replace] skip: idempotency marker present')
            return
        # else 'replace_again': proceed

    prefix = content[:start_m.start()]
    suffix = content[end_m.end():]
    repl = base64.b64decode(op['replacement_base64']).decode('utf-8')

    new_content = prefix + repl + suffix

    if 'verify_preview_sha256' in op:
        preview_hash = sha256_hex(new_content.encode('utf-8'))
        if preview_hash != op['verify_preview_sha256']:
            raise RuntimeError(f'verify_preview_sha256 mismatch: got {preview_hash}, expected {op["verify_preview_sha256"]}')

    if dry_run:
        target = file_path_real
        if shadow_root:
            # Write to shadow location
            target = shadow_root / file_path_real
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(new_content, encoding='utf-8')
            print(f"[replace] shadow write: {target}")
        else:
            print(f"[replace] scan-only: {file_path_real} (no write)")
        return

    # Apply to real FS or shadow_root if provided
    target = file_path_real if shadow_root is None else (shadow_root / file_path_real)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(new_content, encoding='utf-8')
    print(f"[replace] applied: {target}")


def op_write_file(op: dict, ctx: Context, dry_run: bool, shadow_root: Path|None, allowlist, denylist) -> None:
    path_real = Path(ctx.sub(op['path']))
    ensure_allowed(path_real, allowlist, denylist)

    encoding = op.get('encoding', 'utf-8')
    norm = op.get('normalize_eol', 'preserve')

    raw = base64.b64decode(op['content_base64'])
    data = normalize_eol_bytes(raw, norm, encoding)

    expected = op['checksum_sha256']
    actual = sha256_hex(data)
    if expected != actual:
        raise RuntimeError(f"checksum mismatch for {path_real}: expected {expected}, got {actual}")

    if path_real.exists():
        try:
            existing = path_real.read_bytes()
            if sha256_hex(existing) == expected:
                print(f"[write] skip (same): {path_real}")
                return
        except Exception:
            pass
        if 'expected_sha256_before' in op:
            current = sha256_hex(path_real.read_bytes())
            if current != op['expected_sha256_before']:
                raise RuntimeError(f"expected_sha256_before mismatch for {path_real}")
        policy = op.get('if_exists','skip')
        if policy == 'error':
            raise RuntimeError(f"file exists and policy=error: {path_real}")
        if policy == 'skip':
            if dry_run:
                print(f"[write] would overwrite (skipped due to policy): {path_real}")
            else:
                print(f"[write] skip (policy): {path_real}")
            return
        # overwrite allowed

    target = path_real if shadow_root is None else (shadow_root / path_real)

    if dry_run:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        print(f"[write] dry-run {'shadow ' if shadow_root else ''}noop/write: {target}")
        return

    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)
    verify = sha256_hex(target.read_bytes())
    if verify != expected:
        raise RuntimeError(f"post-write checksum mismatch for {target}")
    print(f"[write] wrote: {target}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--plan', default='combined_repo_plan.json')
    ap.add_argument('--phase', choices=['validate','apply','all'], default='all')
    ap.add_argument('--dry-run', dest='dry_run', action='store_true', default=None)
    ap.add_argument('--schema', default=str(Path('.ai/schemas/combined_plan.schema.json')))
    ap.add_argument('--shadow', action='store_true', help='apply writes to a shadow temp dir')
    ap.add_argument('--shadow-dir', help='custom shadow directory path')
    ap.add_argument('--allow', nargs='*', help='override paths_allowlist')
    ap.add_argument('--deny', nargs='*', help='override paths_denylist')
    args = ap.parse_args()

    plan_path = Path(args.plan)
    plan = load_plan(plan_path)

    # Schema validation (optional)
    try:
        validate_schema(plan, Path(args.schema))
    except Exception as e:
        print(f"[error] schema validation failed: {e}")
        sys.exit(1)

    # Fingerprint verification (optional)
    fp = plan.get('plan_fingerprint')
    if fp and fp.get('method') == 'sha256_ops':
        got = sha256_hex(canonicalize_ops(plan.get('ops', [])).encode('utf-8'))
        if got != fp.get('value'):
            print(f"[error] plan fingerprint mismatch: expected {fp.get('value')} got {got}")
            sys.exit(1)

    exec_cfg = plan.get('execution', {})
    dry_run = exec_cfg.get('dry_run', True) if args.dry_run is None else args.dry_run

    # Determine phases
    phases = ['validate','apply'] if args.phase == 'all' else [args.phase]

    # Path constraints
    allowlist = args.allow if args.allow is not None else plan.get('paths_allowlist', [])
    denylist = args.deny if args.deny is not None else plan.get('paths_denylist', [])

    # Shadow directory setup
    shadow_root = None
    if args.shadow:
        shadow_root = Path(args.shadow_dir) if args.shadow_dir else Path(tempfile.mkdtemp(prefix='plan-shadow-'))
        print(f"[shadow] using directory: {shadow_root}")

    ctx = Context()

    # Run ops in order, but honor phase
    for op in plan.get('ops', []):
        op_type = op.get('op')
        op_phase = op.get('phase', 'validate')
        if op_phase not in phases:
            continue
        if op_type == 'locate':
            op_locate(op, ctx)
        elif op_type == 'assert_contains':
            op_assert_contains(op, ctx)
        elif op_type == 'assert_not_contains':
            op_assert_not_contains(op, ctx)
        elif op_type == 'replace_section':
            op_replace_section(op, ctx, dry_run, shadow_root, allowlist, denylist)
        elif op_type == 'write_file':
            op_write_file(op, ctx, dry_run, shadow_root, allowlist, denylist)
        else:
            print(f"[warn] unknown op: {op_type}")

    if shadow_root is not None:
        print(f"[shadow] completed in: {shadow_root}")

if __name__ == '__main__':
    main()
