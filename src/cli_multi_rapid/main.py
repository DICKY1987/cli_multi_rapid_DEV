#!/usr/bin/env python3
"""
CLI Orchestrator Main Entry Point

Provides the main command-line interface for the deterministic, schema-driven
CLI orchestrator that routes between deterministic tools and AI agents.
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
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Show what would be done without executing"
    ),
    files: Optional[str] = typer.Option(
        None, "--files", help="File pattern to process"
    ),
    lane: Optional[str] = typer.Option(None, "--lane", help="Git branch lane for work"),
    max_tokens: Optional[int] = typer.Option(
        None, "--max-tokens", help="Maximum tokens to spend"
    ),
):
    """Run a workflow with schema validation and cost tracking."""
    console.print(f"[bold blue]Running workflow:[/bold blue] {workflow_file}")
    if dry_run:
        console.print("[yellow]DRY RUN mode - no changes will be made[/yellow]")

    # Import here to avoid circular imports during CLI loading
    try:
        from .workflow_runner import WorkflowRunner

        runner = WorkflowRunner()
        result = runner.run(
            workflow_file=workflow_file,
            dry_run=dry_run,
            files=files,
            lane=lane,
            max_tokens=max_tokens,
        )
        if result.success:
            console.print("[green]✓ Workflow completed successfully[/green]")
        else:
            console.print(f"[red]✗ Workflow failed: {result.error}[/red]")
            raise typer.Exit(code=1)
    except ImportError:
        console.print("[red]CLI orchestrator workflow runner not available[/red]")
        console.print("[yellow]Run in basic mode without workflow execution[/yellow]")


@app.command("verify")
def verify_artifact(
    artifact_file: Path = typer.Argument(..., help="Path to artifact JSON file"),
    schema_file: Optional[Path] = typer.Option(
        None, "--schema", help="Path to JSON schema file"
    ),
):
    """Verify an artifact against its JSON schema."""
    console.print(f"[bold blue]Verifying artifact:[/bold blue] {artifact_file}")

    try:
        from .verifier import Verifier

        verifier = Verifier()
        is_valid = verifier.verify_artifact(artifact_file, schema_file)
        if is_valid:
            console.print("[green]✓ Artifact is valid[/green]")
        else:
            console.print("[red]✗ Artifact validation failed[/red]")
            raise typer.Exit(code=1)
    except ImportError:
        console.print("[red]CLI orchestrator verifier not available[/red]")
        raise typer.Exit(code=1)


@app.command("cost")
def cost_report(
    last_run: bool = typer.Option(
        False, "--last-run", help="Show cost for last run only"
    ),
    detailed: bool = typer.Option(
        False, "--detailed", help="Show detailed cost breakdown"
    ),
):
    """Generate cost and token usage reports."""
    console.print("[bold blue]Cost Report[/bold blue]")

    try:
        from .cost_tracker import CostTracker

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
        console.print("[red]CLI orchestrator cost tracker not available[/red]")
        console.print("[yellow]Cost tracking requires full installation[/yellow]")


@app.command("pr")
def create_pr(
    from_dir: Path = typer.Option(
        "artifacts/", "--from", help="Directory containing artifacts"
    ),
    title: str = typer.Option(..., "--title", help="Pull request title"),
    lane: Optional[str] = typer.Option(None, "--lane", help="Git branch lane"),
):
    """Create a pull request from workflow artifacts."""
    console.print(f"[bold blue]Creating PR:[/bold blue] {title}")
    console.print(f"[dim]From artifacts in: {from_dir}[/dim]")

    if lane:
        console.print(f"[dim]Using lane: {lane}[/dim]")

    # Placeholder for PR creation logic
    console.print("[yellow]PR creation functionality not yet implemented[/yellow]")
    console.print("[dim]Would create PR with artifacts from workflow execution[/dim]")


def main():
    """Main entry point for the CLI orchestrator."""
    app()


if __name__ == "__main__":
    main()
