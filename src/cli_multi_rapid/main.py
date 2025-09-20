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


@app.command("codegen-models")
def codegen_models(
    schemas_dir: Path = typer.Option(
        Path("contracts/schemas"), "--schemas", help="Directory with JSON Schemas"
    ),
    out_dir: Path = typer.Option(
        Path("src/contracts/generated"), "--out", help="Output directory for models"
    ),
):
    """Generate Pydantic models from JSON Schemas."""
    console.print("[bold blue]Generating models from schemas[/bold blue]")
    # Defer import to avoid CLI import-time issues
    import os
    import runpy

    env = os.environ.copy()
    env["SCHEMAS_DIR"] = str(schemas_dir)
    env["OUT_DIR"] = str(out_dir)
    script = (
        Path(__file__).resolve().parents[2] / "scripts" / "generate_models.py"
    ).as_posix()
    try:
        runpy.run_path(script_name=script, run_name="__main__")
    except FileNotFoundError:
        console.print("[red]Model generator script not found[/red]")
        raise typer.Exit(code=1)


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


# Tools command group
tools_app = typer.Typer(name="tools", help="Tool management commands")
app.add_typer(tools_app, name="tools")


@tools_app.command("doctor")
def tools_doctor():
    """Check health and availability of all configured tools."""
    console.print("[bold blue]Running tool health check...[/bold blue]")

    try:
        import sys
        from pathlib import Path

        # Add src to path to find integrations
        src_path = Path(__file__).parent.parent.parent
        if str(src_path) not in sys.path:
            sys.path.insert(0, str(src_path))

        from integrations.process import ProcessRunner
        from integrations.registry import detect_all, generate_doctor_report

        runner = ProcessRunner()
        probes = detect_all(runner)
        report = generate_doctor_report(probes)

        console.print(report)

        # Exit with non-zero if any critical tools are missing
        failed_tools = [name for name, probe in probes.items() if not probe.ok]
        if failed_tools:
            console.print(f"\n[red]Failed tools: {', '.join(failed_tools)}[/red]")
            raise typer.Exit(code=1)

    except ImportError:
        console.print("[red]Tool integration layer not available[/red]")
        raise typer.Exit(code=1)


@tools_app.command("list")
def tools_list():
    """List all configured tools with their paths and versions."""
    console.print("[bold blue]Configured Tools[/bold blue]")

    try:
        import sys
        from pathlib import Path

        # Add src to path to find integrations
        src_path = Path(__file__).parent.parent.parent
        if str(src_path) not in sys.path:
            sys.path.insert(0, str(src_path))

        from integrations.process import ProcessRunner
        from integrations.registry import detect_all

        runner = ProcessRunner()
        probes = detect_all(runner)

        table = Table(title="Tool Configuration")
        table.add_column("Tool", style="cyan")
        table.add_column("Status", style="green")
        table.add_column("Version", style="yellow")
        table.add_column("Path", style="dim")

        for name, probe in probes.items():
            status = "✓" if probe.ok else "✗"
            version = probe.version or "unknown"
            path = probe.path or "not found"
            table.add_row(name, status, version, path)

        console.print(table)

    except ImportError:
        console.print("[red]Tool integration layer not available[/red]")


@tools_app.command("versions")
def tools_versions():
    """Show version information for all tools."""
    console.print("[bold blue]Tool Versions[/bold blue]")

    try:
        from ..integrations.process import ProcessRunner
        from ..integrations.registry import detect_all

        runner = ProcessRunner()
        probes = detect_all(runner)

        for name, probe in probes.items():
            if probe.ok and probe.version:
                console.print(f"✓ {name}: {probe.version}")
            else:
                console.print(f"✗ {name}: not available")

    except ImportError:
        console.print("[red]Tool integration layer not available[/red]")


# Quality command group
quality_app = typer.Typer(name="quality", help="Python code quality commands")
app.add_typer(quality_app, name="quality")


@quality_app.command("run")
def quality_run(
    fix: bool = typer.Option(False, "--fix", help="Auto-fix issues where possible"),
    paths: Optional[str] = typer.Option(
        None, "--paths", help="Paths to check (comma-separated)"
    ),
):
    """Run Python code quality checks (ruff, mypy, bandit, semgrep)."""
    console.print("[bold blue]Running Python quality checks...[/bold blue]")

    try:
        from ..integrations.process import ProcessRunner
        from ..integrations.python_quality import create_python_quality_adapter

        runner = ProcessRunner()
        quality_adapter = create_python_quality_adapter(runner)

        # Parse paths if provided
        path_list = None
        if paths:
            path_list = [p.strip() for p in paths.split(",")]

        # Run all quality tools
        results = quality_adapter.run_all(fix=fix, paths=path_list)

        # Display results
        for tool_name, result in results.items():
            status = "✓ PASS" if result.code == 0 else "✗ FAIL"
            console.print(f"{status} {tool_name} ({result.duration_s:.2f}s)")

            if result.stdout:
                console.print(f"[dim]{result.stdout.strip()}[/dim]")
            if result.code != 0 and result.stderr:
                console.print(f"[red]{result.stderr.strip()}[/red]")

        # Generate summary
        summary = quality_adapter.generate_summary(results)
        console.print(f"\n{summary}")

        # Exit with error if any tool failed
        failed_count = sum(1 for r in results.values() if r.code != 0)
        if failed_count > 0:
            raise typer.Exit(code=1)

    except ImportError:
        console.print("[red]Python quality tools not available[/red]")
        raise typer.Exit(code=1)


# Containers command group
containers_app = typer.Typer(name="containers", help="Container management commands")
app.add_typer(containers_app, name="containers")


@containers_app.command("up")
def containers_up(
    compose_file: str = typer.Option(
        "docker-compose.yml", "--file", "-f", help="Compose file path"
    ),
    detach: bool = typer.Option(True, "--detach", "-d", help="Run in background"),
):
    """Start containers with docker-compose."""
    console.print(f"[bold blue]Starting containers from {compose_file}...[/bold blue]")

    try:
        from ..integrations.containers import create_containers_adapter
        from ..integrations.process import ProcessRunner

        runner = ProcessRunner()
        containers = create_containers_adapter(runner)

        result = containers.compose_up(compose_file=compose_file, detach=detach)

        if result.code == 0:
            console.print("[green]✓ Containers started successfully[/green]")
        else:
            console.print(f"[red]✗ Failed to start containers: {result.stderr}[/red]")
            raise typer.Exit(code=1)

    except ImportError:
        console.print("[red]Container tools not available[/red]")
        raise typer.Exit(code=1)


@containers_app.command("down")
def containers_down(
    compose_file: str = typer.Option(
        "docker-compose.yml", "--file", "-f", help="Compose file path"
    ),
):
    """Stop containers with docker-compose."""
    console.print(f"[bold blue]Stopping containers from {compose_file}...[/bold blue]")

    try:
        from ..integrations.containers import create_containers_adapter
        from ..integrations.process import ProcessRunner

        runner = ProcessRunner()
        containers = create_containers_adapter(runner)

        result = containers.compose_down(compose_file=compose_file)

        if result.code == 0:
            console.print("[green]✓ Containers stopped successfully[/green]")
        else:
            console.print(f"[red]✗ Failed to stop containers: {result.stderr}[/red]")
            raise typer.Exit(code=1)

    except ImportError:
        console.print("[red]Container tools not available[/red]")
        raise typer.Exit(code=1)


@containers_app.command("ps")
def containers_ps():
    """List running containers."""
    try:
        from ..integrations.containers import create_containers_adapter
        from ..integrations.process import ProcessRunner

        runner = ProcessRunner()
        containers = create_containers_adapter(runner)

        result = containers.ps()

        if result.code == 0:
            console.print("[bold blue]Running Containers:[/bold blue]")
            console.print(result.stdout)
        else:
            console.print(f"[red]✗ Failed to list containers: {result.stderr}[/red]")
            raise typer.Exit(code=1)

    except ImportError:
        console.print("[red]Container tools not available[/red]")
        raise typer.Exit(code=1)


# Repo command group
repo_app = typer.Typer(name="repo", help="Repository management commands")
app.add_typer(repo_app, name="repo")


@repo_app.command("clone")
def repo_clone(
    url: str = typer.Argument(..., help="Repository URL to clone"),
    target_dir: str = typer.Argument(..., help="Target directory"),
    use_gh: bool = typer.Option(False, "--gh", help="Use GitHub CLI instead of git"),
):
    """Clone a repository."""
    console.print(f"[bold blue]Cloning {url} to {target_dir}...[/bold blue]")

    try:
        from ..integrations.process import ProcessRunner
        from ..integrations.vcs import create_vcs_adapter

        runner = ProcessRunner()
        vcs = create_vcs_adapter(runner, "gh" if use_gh else "git")

        result = vcs.clone(url, target_dir)

        if result.code == 0:
            console.print("[green]✓ Repository cloned successfully[/green]")
        else:
            console.print(f"[red]✗ Failed to clone repository: {result.stderr}[/red]")
            raise typer.Exit(code=1)

    except ImportError:
        console.print("[red]VCS tools not available[/red]")
        raise typer.Exit(code=1)


@repo_app.command("status")
def repo_status(
    cwd: Optional[str] = typer.Option(None, "--cwd", help="Repository directory"),
):
    """Get repository status."""
    try:
        from ..integrations.process import ProcessRunner
        from ..integrations.vcs import create_vcs_adapter

        runner = ProcessRunner()
        vcs = create_vcs_adapter(runner)

        result = vcs.status(cwd=cwd)

        if result.code == 0:
            console.print("[bold blue]Repository Status:[/bold blue]")
            console.print(result.stdout)
        else:
            console.print(f"[red]✗ Failed to get status: {result.stderr}[/red]")
            raise typer.Exit(code=1)

    except ImportError:
        console.print("[red]VCS tools not available[/red]")
        raise typer.Exit(code=1)


# AI command group
ai_app = typer.Typer(name="ai", help="AI CLI commands")
app.add_typer(ai_app, name="ai")


@ai_app.command("run")
def ai_run(
    provider: str = typer.Option(
        "claude", "--provider", help="AI provider (claude|openai)"
    ),
    command: str = typer.Argument(..., help="Command to run"),
    cwd: Optional[str] = typer.Option(None, "--cwd", help="Working directory"),
):
    """Run AI CLI commands."""
    console.print(f"[bold blue]Running {provider} command: {command}[/bold blue]")

    try:
        from ..integrations.ai_cli import create_ai_cli_adapter
        from ..integrations.process import ProcessRunner

        runner = ProcessRunner()
        ai_cli = create_ai_cli_adapter(runner, provider)

        # Parse command into arguments
        import shlex

        args = shlex.split(command)

        result = ai_cli.run_command(args, cwd=cwd)

        if result.stdout:
            console.print(result.stdout)
        if result.stderr:
            console.print(f"[red]{result.stderr}[/red]")

        if result.code != 0:
            raise typer.Exit(code=result.code)

    except ImportError:
        console.print("[red]AI CLI tools not available[/red]")
        raise typer.Exit(code=1)


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

    try:
        from ..integrations.process import ProcessRunner
        from ..integrations.vcs import create_vcs_adapter

        runner = ProcessRunner()
        vcs = create_vcs_adapter(runner, "gh")  # Use GitHub CLI for PR creation

        # Create basic PR (this is a simplified implementation)
        result = vcs.pr_create(title, f"Auto-generated PR from artifacts in {from_dir}")

        if result.code == 0:
            console.print("[green]✓ Pull request created successfully[/green]")
            console.print(result.stdout)
        else:
            console.print(f"[red]✗ Failed to create PR: {result.stderr}[/red]")
            raise typer.Exit(code=1)

    except ImportError:
        console.print("[red]VCS tools not available[/red]")
        console.print("[yellow]PR creation requires GitHub CLI integration[/yellow]")
        raise typer.Exit(code=1)


def main():
    """Main entry point for the CLI orchestrator."""
    app()


if __name__ == "__main__":
    main()
