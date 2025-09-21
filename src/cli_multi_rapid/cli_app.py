from pathlib import Path
from typing import Optional

import typer
from rich.console import Console


app = typer.Typer(
    name="cli-orchestrator",
    help="Deterministic, Schema-Driven CLI Orchestrator (minimal CLI)",
    rich_markup_mode="rich",
)
console = Console()


@app.command("verify")
def verify_cmd(
    artifact_file: Path = typer.Argument(..., help="Path to artifact JSON file"),
    schema_file: Optional[Path] = typer.Option(
        None, "--schema", help="Path to JSON schema file"
    ),
) -> None:
    """Verify an artifact against its JSON schema (via Verifier)."""
    try:
        from .verifier import Verifier  # use recovered implementation if available
    except Exception:  # pragma: no cover - fallback for local dev/tests
        from .simple_verifier import Verifier

    v = Verifier()
    ok = v.verify_artifact(artifact_file, schema_file)
    if ok:
        console.print("[green]OK: Artifact is valid[/green]")
    else:
        console.print("[red]FAIL: Artifact validation failed[/red]")
        raise typer.Exit(code=1)
