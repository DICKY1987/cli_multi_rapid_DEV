from __future__ import annotations

import json
from typing import Any, Dict

from integrations.process import ProcessRunner
from integrations.registry_tools import detect_all


def main() -> int:
    runner = ProcessRunner(dry_run=False)
    probes = detect_all(runner)
    ok = True
    report: Dict[str, Any] = {}
    for name, probe in probes.items():
        report[name] = {
            "ok": probe.ok,
            "version": probe.version,
            "path": probe.path,
            "details": probe.details,
        }
        if not probe.ok:
            ok = False
    print(json.dumps(report, indent=2))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())

