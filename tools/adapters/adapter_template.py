#!/usr/bin/env python3
import argparse
import json
import pathlib
import sys
import time
from uuid import uuid4

EXIT_OK, EXIT_PARTIAL, EXIT_VALIDATION, EXIT_USAGE, EXIT_DEP, EXIT_INTERNAL = (
    0,
    10,
    20,
    30,
    40,
    50,
)
IO_VERSION = "io.v1"


def eprint(*a, **k):
    print(*a, file=sys.stderr, **k)


def emit_event(run_id, typ, msg, data=None, step=None):
    evt = {
        "version": IO_VERSION,
        "id": run_id,
        "type": typ,
        "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "message": msg,
    }
    if data is not None:
        evt["data"] = data
    if step:
        evt["step"] = step
    print("##io_event " + json.dumps(evt), flush=True)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--io-mode", choices=["json", "files"], default="json")
    p.add_argument("--io-in", default="-")
    p.add_argument("--io-out", default="-")
    p.add_argument("--io-events", default="stdout")
    p.add_argument("--io-artifacts-dir", default=".apf/run")
    args, _unknown = p.parse_known_args()

    raw = (
        sys.stdin.read()
        if args.io_in == "-"
        else pathlib.Path(args.io_in).read_text(encoding="utf-8")
    )
    try:
        req = json.loads(raw)
    except Exception as ex:
        eprint("Invalid JSON input:", ex)
        resp = {
            "version": IO_VERSION,
            "id": str(uuid4()),
            "status": "error",
            "exit_code": EXIT_USAGE,
            "errors": [{"code": "bad_input", "message": "Invalid JSON"}],
        }
        print(json.dumps(resp, ensure_ascii=False))
        return EXIT_USAGE

    run_id = req.get("id") or str(uuid4())
    if req.get("version") != IO_VERSION:
        emit_event(
            run_id,
            "error",
            "Protocol version mismatch",
            {"expected": IO_VERSION, "got": req.get("version")},
        )
        resp = {
            "version": IO_VERSION,
            "id": run_id,
            "status": "error",
            "exit_code": EXIT_VALIDATION,
            "errors": [{"code": "version_mismatch", "message": "Unsupported version"}],
        }
        print(json.dumps(resp))
        return EXIT_VALIDATION

    t0 = time.time()
    emit_event(run_id, "progress", "Starting task", step="init")

    patches = []
    report = {"summary": "No-op adapter example", "changes": 0}

    duration_ms = int((time.time() - t0) * 1000)
    resp = {
        "version": IO_VERSION,
        "id": run_id,
        "status": "ok",
        "exit_code": EXIT_OK,
        "outputs": {"report": report, "patches": patches},
        "metrics": {"duration_ms": duration_ms},
    }
    out_s = json.dumps(resp, ensure_ascii=False)
    if args.io_out == "-":
        print(out_s)
    else:
        pathlib.Path(args.io_out).write_text(out_s, encoding="utf-8")
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
