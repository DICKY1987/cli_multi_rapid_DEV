#!/usr/bin/env python3
"""CLI Orchestrator Main Entry Point

Schema-driven CLI that routes between deterministic tools and AI agents.
This implementation provides stable commands that defer to optional modules
when available, and print helpful messages otherwise.
"""

from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table


app = typer.Typer(
    name="cli-orchestrator",
    help="Deterministic, Schema-Driven CLI Orchestrator",
    rich_markup_mode="rich",
)
console = Console()


@app.command("run")
def run_workflow(
    workflow_file: Path = typer.Argument(..., help="Path to workflow YAML file"),
    dry_run: bool = typer.Option(False, "--dry-run", help="No-op run"),
    files: Optional[str] = typer.Option(None, "--files", help="File pattern to process"),
    lane: Optional[str] = typer.Option(None, "--lane", help="Git branch lane for work"),
    max_tokens: Optional[int] = typer.Option(None, "--max-tokens", help="Token budget"),
) -> None:
    """Run a workflow with schema validation and cost tracking."""
    console.print(f"[bold blue]Running workflow:[/bold blue] {workflow_file}")
    if dry_run:
        console.print("[yellow]DRY RUN mode - no changes will be made[/yellow]")

    try:
        from .workflow_runner import WorkflowRunner  # type: ignore

        runner = WorkflowRunner()
        result = runner.run(
            workflow_file=workflow_file,
            dry_run=dry_run,
            files=files,
            lane=lane,
            max_tokens=max_tokens,
        )
        if getattr(result, "success", False):
            console.print("[green]OK: Workflow completed successfully[/green]")
        else:
            error = getattr(result, "error", "unknown error")
            console.print(f"[red]FAIL: Workflow failed: {error}[/red]")
            raise typer.Exit(code=1)
    except ImportError:
        console.print("[red]Workflow runner not available[/red]")
        console.print("[yellow]Install full package to enable execution[/yellow]")


@app.command("verify")
def verify_artifact(
    artifact_file: Path = typer.Argument(..., help="Path to artifact JSON file"),
    schema_file: Optional[Path] = typer.Option(None, "--schema", help="Path to JSON schema file"),
) -> None:
    """Verify an artifact against its JSON schema."""
    try:
        from .verifier import Verifier
    except Exception:  # pragma: no cover
        console.print("[red]Verifier implementation missing[/red]")
        raise typer.Exit(code=1)

    console.print(f"[bold blue]Verifying artifact:[/bold blue] {artifact_file}")
    verifier = Verifier()
    is_valid = verifier.verify_artifact(artifact_file, schema_file)
    if is_valid:
        console.print("[green]OK: Artifact is valid[/green]")
    else:
        console.print("[red]FAIL: Artifact validation failed[/red]")
        raise typer.Exit(code=1)


@app.command("cost")
def cost_report(
    last_run: bool = typer.Option(False, "--last-run", help="Show last run only"),
    detailed: bool = typer.Option(False, "--detailed", help="Show breakdown"),
) -> None:
    """Generate cost and token usage reports."""
    console.print("[bold blue]Cost Report[/bold blue]")
    try:
        from .cost_tracker import CostTracker  # type: ignore

        tracker = CostTracker()
        report = tracker.generate_report(last_run=last_run, detailed=detailed)
        table = Table(title="Token Usage Summary")
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="magenta")
        table.add_row("Total Tokens", str(report.get("total_tokens", 0)))
        table.add_row("Estimated Cost", f"${report.get('estimated_cost', 0.0):.4f}")
        table.add_row("Runs Today", str(report.get("runs_today", 0)))
        console.print(table)
    except ImportError:
        console.print("[yellow]Cost tracker not available in this build[/yellow]")

