#!/usr/bin/env python3
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ANALYSIS = ROOT / "artifacts" / "analysis" / "enhanced_findings_v3.json"
OUT_DIR = ROOT / "artifacts" / "planning"


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    findings = json.loads(ANALYSIS.read_text(encoding="utf-8"))
    items = findings.get("findings", [])

    # Simple mapping: each finding becomes a task
    tasks = []
    for i, f in enumerate(items, 1):
        tasks.append(
            {
                "id": f["id"].replace("-", "_"),
                "title": f["description"][:80],
                "type": (
                    "architecture_refactoring"
                    if f["domain"] in {"structural", "code"}
                    else "operational_improvement"
                ),
                "priority": "medium" if f["severity"] == "MAJOR" else "low",
                "complexity": "medium",
                "owner": "dev",
                "depends_on": [],
            }
        )

    roadmap = {
        "generated": datetime.utcnow().isoformat(),
        "phases": [
            {"id": "phase_foundation", "tasks": [t["id"] for t in tasks[:2]]},
            {"id": "phase_improvements", "tasks": [t["id"] for t in tasks[2:]]},
        ],
        "tasks": tasks,
    }
    (OUT_DIR / "implementation_roadmap_v3.json").write_text(
        json.dumps(roadmap, indent=2), encoding="utf-8"
    )

    resource_alloc = {
        "generated": datetime.utcnow().isoformat(),
        "roles": [
            {"role": "dev", "count": 2},
            {"role": "ops", "count": 1},
        ],
        "estimates": {t["id"]: {"effort": "M"} for t in tasks},
    }
    (OUT_DIR / "resource_allocation_v3.json").write_text(
        json.dumps(resource_alloc, indent=2), encoding="utf-8"
    )

    risk_matrix = {
        "generated": datetime.utcnow().isoformat(),
        "risks": [
            {
                "id": "R1",
                "level": "medium",
                "desc": "CI instability in extended job",
                "mitigation": "run-only on Ubuntu",
            },
            {
                "id": "R2",
                "level": "low",
                "desc": "Optional-dep import fragility",
                "mitigation": "importorskip + mocks",
            },
        ],
    }
    (OUT_DIR / "risk_matrix_v1.json").write_text(
        json.dumps(risk_matrix, indent=2), encoding="utf-8"
    )
    print(str(OUT_DIR))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
