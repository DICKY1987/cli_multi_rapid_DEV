import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

from rich.console import Console


console = Console()


@dataclass
class GateResult:
    gate_name: str
    passed: bool
    message: str
    details: dict[str, Any] | None = None

    def __post_init__(self) -> None:
        if self.details is None:
            self.details = {}


class Verifier:
    """Minimal verifier used when the full recovered verifier cannot be imported."""

    def verify_artifact(self, artifact_file: Path, schema_file: Optional[Path] = None) -> bool:
        if not artifact_file.exists():
            console.print(f"[red]Artifact file not found: {artifact_file}[/red]")
            return False
        with open(artifact_file, encoding="utf-8") as f:
            artifact = json.load(f)

        # If schema provided, try to validate with jsonschema
        if schema_file and schema_file.exists():
            try:
                import jsonschema

                with open(schema_file, encoding="utf-8") as f:
                    schema = json.load(f)
                jsonschema.validate(artifact, schema)
                return True
            except Exception:
                return False

        # Basic validation fallback
        return all(k in artifact for k in ("timestamp", "type"))

