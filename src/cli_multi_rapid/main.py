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


# Enhanced functionality command group
enhanced_app = typer.Typer(name="enhanced", help="Enhanced CLI orchestrator features")
app.add_typer(enhanced_app, name="enhanced")


@enhanced_app.command("parallel")
def run_parallel_workflow(
    workflow_file: Path = typer.Argument(..., help="Path to workflow YAML file"),
    max_concurrent: int = typer.Option(
        4, "--concurrent", help="Maximum concurrent steps"
    ),
    dry_run: bool = typer.Option(False, "--dry-run", help="Show what would be done"),
    files: Optional[str] = typer.Option(
        None, "--files", help="File pattern to process"
    ),
    lane: Optional[str] = typer.Option(None, "--lane", help="Git branch lane"),
    optimize: bool = typer.Option(
        True, "--optimize/--no-optimize", help="Apply optimization"
    ),
):
    """Run a workflow with parallel execution."""
    console.print(
        f"[bold blue]Running workflow in parallel mode:[/bold blue] {workflow_file}"
    )
    console.print(f"[dim]Max concurrent: {max_concurrent}[/dim]")

    try:
        from .workflow_runner import WorkflowRunner

        runner = WorkflowRunner(parallel_enabled=True, max_concurrent=max_concurrent)
        result = runner.run(
            workflow_file=workflow_file,
            dry_run=dry_run,
            files=files,
            lane=lane,
            parallel=True,
            optimize=optimize,
        )

        if result.success:
            console.print("[green]✓ Parallel workflow completed successfully[/green]")
            if result.parallel_stats:
                stats = result.parallel_stats
                console.print(
                    f"[dim]Completed: {len(stats.get('completed_nodes', []))} nodes[/dim]"
                )
                console.print(
                    f"[dim]Failed: {len(stats.get('failed_nodes', []))} nodes[/dim]"
                )
        else:
            console.print(f"[red]✗ Parallel workflow failed: {result.error}[/red]")
            raise typer.Exit(code=1)
    except ImportError:
        console.print("[red]Enhanced workflow runner not available[/red]")
        raise typer.Exit(code=1)


@enhanced_app.command("optimize")
def optimize_workflow(
    plan_file: Path = typer.Argument(..., help="Path to workflow or plan file"),
    priority: str = typer.Option(
        "balanced",
        "--priority",
        help="Optimization priority (cost|speed|quality|balanced)",
    ),
    output: Optional[Path] = typer.Option(
        None, "--output", help="Output file for optimized plan"
    ),
):
    """Optimize a workflow plan using predictive analytics."""
    console.print(f"[bold blue]Optimizing workflow plan:[/bold blue] {plan_file}")
    console.print(f"[dim]Priority: {priority}[/dim]")

    try:
        from .lib.optimizer import optimize_plan_command

        success = optimize_plan_command(
            str(plan_file),
            priority=priority,
            output_file=str(output) if output else None,
        )

        if success:
            console.print("[green]✓ Workflow optimization completed[/green]")
        else:
            console.print("[red]✗ Workflow optimization failed[/red]")
            raise typer.Exit(code=1)
    except ImportError:
        console.print("[red]Workflow optimizer not available[/red]")
        raise typer.Exit(code=1)


@enhanced_app.command("template")
def generate_template(
    request: str = typer.Argument(
        ..., help="Natural language description of desired workflow"
    ),
    name: Optional[str] = typer.Option(None, "--name", help="Template name"),
    output: Optional[Path] = typer.Option(None, "--output", help="Custom output path"),
):
    """Generate a workflow template from natural language description."""
    console.print(f"[bold blue]Generating template:[/bold blue] {request}")

    try:
        import asyncio

        from .lib.templates import smart_template_command

        result = asyncio.run(
            smart_template_command(
                request, template_name=name, save_path=str(output) if output else None
            )
        )

        console.print(f"[green]✓ Template generated:[/green] {result['template_path']}")
        console.print(
            f"[dim]Intent: {result['intent'].type} (confidence: {result['intent'].confidence:.2f})[/dim]"
        )
        console.print(
            f"[dim]Technologies: {', '.join(result['intent'].technologies)}[/dim]"
        )

    except ImportError:
        console.print("[red]Template generator not available[/red]")
        raise typer.Exit(code=1)


@enhanced_app.command("dev")
def dev_mode(
    watch_dir: Path = typer.Option(
        Path(".ai/workflows"), "--watch", help="Directory to watch for changes"
    ),
):
    """Start development mode with hot reload."""
    console.print("[bold blue]Starting development mode...[/bold blue]")
    console.print(f"[dim]Watching: {watch_dir}[/dim]")

    try:
        import asyncio

        from .lib.hot_reload import dev_mode_command

        asyncio.run(dev_mode_command(str(watch_dir)))

    except ImportError:
        console.print("[red]Hot reload system not available[/red]")
        raise typer.Exit(code=1)
    except KeyboardInterrupt:
        console.print("\n[yellow]Development mode stopped[/yellow]")


@enhanced_app.command("analyze")
def analyze_performance(
    artifacts_dir: Path = typer.Option(
        Path("artifacts"), "--artifacts", help="Artifacts directory"
    ),
):
    """Analyze workflow performance and generate insights."""
    console.print(f"[bold blue]Analyzing performance from:[/bold blue] {artifacts_dir}")

    try:
        from .lib.optimizer import analyze_performance_command

        stats = analyze_performance_command(str(artifacts_dir))

        if stats.get("error"):
            console.print(f"[red]✗ {stats['error']}[/red]")
            raise typer.Exit(code=1)

        # Display performance statistics
        table = Table(title="Performance Analysis")
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="magenta")

        table.add_row("Tools Analyzed", str(stats.get("total_tools_analyzed", 0)))
        table.add_row("Total Executions", str(stats.get("total_executions", 0)))

        best_performers = stats.get("best_performers", {})
        table.add_row(
            "Most Cost Efficient", best_performers.get("cost_efficient", "N/A")
        )
        table.add_row("Fastest", best_performers.get("fastest", "N/A"))
        table.add_row("Highest Quality", best_performers.get("highest_quality", "N/A"))

        console.print(table)

    except ImportError:
        console.print("[red]Performance analyzer not available[/red]")
        raise typer.Exit(code=1)


@enhanced_app.command("templates")
def list_templates():
    """List all available workflow templates."""
    console.print("[bold blue]Available Templates[/bold blue]")

    try:
        from .lib.templates import list_templates_command

        templates = list_templates_command()

        if not templates:
            console.print("[yellow]No templates found[/yellow]")
            return

        table = Table(title="Workflow Templates")
        table.add_column("Name", style="cyan")
        table.add_column("Description", style="dim")
        table.add_column("Created", style="yellow")

        for template in templates:
            created = template.get("metadata", {}).get("generated_at", "Unknown")
            if created != "Unknown":
                try:
                    from datetime import datetime

                    dt = datetime.fromisoformat(created.replace("Z", "+00:00"))
                    created = dt.strftime("%Y-%m-%d %H:%M")
                except:
                    pass

            table.add_row(
                template["name"],
                (
                    template["description"][:60] + "..."
                    if len(template["description"]) > 60
                    else template["description"]
                ),
                created,
            )

        console.print(table)

    except ImportError:
        console.print("[red]Template system not available[/red]")
        raise typer.Exit(code=1)


@enhanced_app.command("stats")
def routing_stats():
    """Show intelligent routing statistics."""
    console.print("[bold blue]Routing Statistics[/bold blue]")

    try:
        from .router import Router

        router = Router()
        stats = router.get_routing_statistics()

        if stats.get("total_decisions", 0) == 0:
            console.print("[yellow]No routing decisions recorded yet[/yellow]")
            return

        table = Table(title="Intelligent Routing Stats")
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="magenta")

        table.add_row("Total Decisions", str(stats["total_decisions"]))
        table.add_row("Optimization Rate", f"{stats['optimization_rate']:.1%}")
        table.add_row("Average Confidence", f"{stats['average_confidence']:.2f}")
        table.add_row("Most Used Adapter", stats.get("most_used_adapter", "N/A"))

        console.print(table)

        # Show adapter usage breakdown
        if stats.get("adapter_usage"):
            usage_table = Table(title="Adapter Usage")
            usage_table.add_column("Adapter", style="cyan")
            usage_table.add_column("Count", style="magenta")
            usage_table.add_column("Percentage", style="yellow")

            total = stats["total_decisions"]
            for adapter, count in stats["adapter_usage"].items():
                percentage = (count / total) * 100
                usage_table.add_row(adapter, str(count), f"{percentage:.1f}%")

            console.print(usage_table)

    except ImportError:
        console.print("[red]Enhanced router not available[/red]")
        raise typer.Exit(code=1)


# Recovery command group
recovery_app = typer.Typer(name="recovery", help="Error recovery commands")
app.add_typer(recovery_app, name="recovery")


@recovery_app.command("analyze")
def analyze_error(
    error_log: Optional[Path] = typer.Option(
        None, "--log", help="Path to error log file"
    ),
    error_text: Optional[str] = typer.Option(
        None, "--text", help="Error text to analyze"
    ),
):
    """Analyze an error and suggest recovery options."""
    if not error_log and not error_text:
        console.print("[red]Either --log or --text must be provided[/red]")
        raise typer.Exit(code=1)

    try:
        from .lib.error_recovery import IntelligentErrorRecovery

        recovery = IntelligentErrorRecovery()

        if error_log:
            with open(error_log) as f:
                error_content = f.read()
        else:
            error_content = error_text

        result = recovery.diagnose_error(error_content)

        if result:
            pattern, details = result
            console.print("[bold blue]Error Analysis[/bold blue]")
            console.print(f"Pattern: {pattern.fix_strategy}")
            console.print(f"Severity: {pattern.severity.value}")
            console.print(f"Auto-fixable: {'Yes' if pattern.auto_fixable else 'No'}")
            console.print(f"Confidence: {pattern.confidence:.2f}")

            if pattern.auto_fixable:
                console.print("[green]This error can be automatically fixed[/green]")

                fix = typer.confirm("Attempt automatic fix?")
                if fix:
                    success = recovery.attempt_recovery(pattern, details)
                    if success:
                        console.print("[green]✓ Recovery successful[/green]")
                    else:
                        console.print("[red]✗ Recovery failed[/red]")
            else:
                console.print("[yellow]Manual intervention required[/yellow]")
        else:
            console.print("[yellow]No known recovery pattern found[/yellow]")

    except ImportError:
        console.print("[red]Error recovery system not available[/red]")
        raise typer.Exit(code=1)


@recovery_app.command("stats")
def recovery_stats():
    """Show error recovery statistics."""
    console.print("[bold blue]Error Recovery Statistics[/bold blue]")

    try:
        from .lib.error_recovery import IntelligentErrorRecovery

        recovery = IntelligentErrorRecovery()
        stats = recovery.get_recovery_stats()

        if stats.get("total_attempts", 0) == 0:
            console.print("[yellow]No recovery attempts recorded[/yellow]")
            return

        table = Table(title="Recovery Statistics")
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="magenta")

        table.add_row("Total Attempts", str(stats["total_attempts"]))
        table.add_row("Successful", str(stats["successful_attempts"]))
        table.add_row("Success Rate", f"{stats['success_rate']:.1%}")

        console.print(table)

        # Show strategy breakdown
        if stats.get("strategy_stats"):
            strategy_table = Table(title="Recovery Strategies")
            strategy_table.add_column("Strategy", style="cyan")
            strategy_table.add_column("Attempts", style="magenta")
            strategy_table.add_column("Success Rate", style="yellow")

            for strategy, data in stats["strategy_stats"].items():
                success_rate = (
                    (data["successful"] / data["total"]) if data["total"] > 0 else 0
                )
                strategy_table.add_row(
                    strategy, str(data["total"]), f"{success_rate:.1%}"
                )

            console.print(strategy_table)

    except ImportError:
        console.print("[red]Error recovery system not available[/red]")
        raise typer.Exit(code=1)


@app.command("preflight")
def preflight_check(
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show detailed output"),
    json_output: bool = typer.Option(False, "--json", help="Output in JSON format"),
    strict: bool = typer.Option(
        True, "--strict/--no-strict", help="Strict validation mode"
    ),
):
    """Run preflight checks to validate system readiness."""
    console.print("[bold blue]Running preflight checks...[/bold blue]")

    try:
        import json as jsonlib
        from pathlib import Path

        from .adapters.adapter_registry import AdapterRegistry
        from .enterprise.config import Configuration
        from .enterprise.health_checks import HealthCheckManager

        checks_passed = 0
        total_checks = 0
        results = {"status": "UNKNOWN", "checks": {}, "errors": []}

        # 1. Configuration validation
        total_checks += 1
        try:
            config = Configuration()
            config.validate()
            checks_passed += 1
            results["checks"]["configuration"] = {
                "status": "PASS",
                "message": "Configuration valid",
            }
            if verbose:
                console.print("[green]✓ Configuration validation passed[/green]")
        except Exception as e:
            results["checks"]["configuration"] = {"status": "FAIL", "message": str(e)}
            results["errors"].append(f"Configuration: {e}")
            if verbose:
                console.print(f"[red]✗ Configuration validation failed: {e}[/red]")

        # 2. Schema presence
        total_checks += 1
        required_schemas = [
            ".ai/schemas/plan.schema.json",
            ".ai/schemas/events/ProgressEvent.schema.json",
            ".ai/schemas/artifacts/result_manifest.schema.json",
        ]
        missing_schemas = [s for s in required_schemas if not Path(s).exists()]
        if not missing_schemas:
            checks_passed += 1
            results["checks"]["schemas"] = {
                "status": "PASS",
                "message": "All required schemas present",
            }
            if verbose:
                console.print("[green]✓ Required schemas present[/green]")
        else:
            results["checks"]["schemas"] = {
                "status": "FAIL",
                "message": f"Missing schemas: {missing_schemas}",
            }
            results["errors"].append(f"Missing schemas: {missing_schemas}")
            if verbose:
                console.print(f"[red]✗ Missing schemas: {missing_schemas}[/red]")

        # 3. Health checks
        total_checks += 1
        try:
            health_manager = HealthCheckManager()
            health_manager.add_default_checks()
            health_status = health_manager.check_all()

            if health_status.overall_status == "HEALTHY":
                checks_passed += 1
                results["checks"]["health"] = {
                    "status": "PASS",
                    "message": "All health checks passed",
                }
                if verbose:
                    console.print("[green]✓ Health checks passed[/green]")
            else:
                failed_checks = [
                    name
                    for name, check in health_status.checks.items()
                    if check.status != "HEALTHY"
                ]
                results["checks"]["health"] = {
                    "status": "FAIL",
                    "message": f"Failed health checks: {failed_checks}",
                }
                results["errors"].append(f"Health checks failed: {failed_checks}")
                if verbose:
                    console.print(f"[red]✗ Health checks failed: {failed_checks}[/red]")
        except Exception as e:
            results["checks"]["health"] = {"status": "FAIL", "message": str(e)}
            results["errors"].append(f"Health checks: {e}")
            if verbose:
                console.print(f"[red]✗ Health checks failed: {e}[/red]")

        # 4. Adapter availability
        total_checks += 1
        try:
            registry = AdapterRegistry()
            available_adapters = registry.get_available_adapters()
            if available_adapters:
                checks_passed += 1
                results["checks"]["adapters"] = {
                    "status": "PASS",
                    "message": f"Found {len(available_adapters)} adapters",
                }
                if verbose:
                    console.print(
                        f"[green]✓ {len(available_adapters)} adapters available[/green]"
                    )
            else:
                results["checks"]["adapters"] = {
                    "status": "FAIL",
                    "message": "No adapters available",
                }
                results["errors"].append("No adapters available")
                if verbose:
                    console.print("[red]✗ No adapters available[/red]")
        except Exception as e:
            results["checks"]["adapters"] = {"status": "FAIL", "message": str(e)}
            results["errors"].append(f"Adapters: {e}")
            if verbose:
                console.print(f"[red]✗ Adapter check failed: {e}[/red]")

        # 5. Directory writability
        total_checks += 1
        try:
            artifacts_dir = Path("artifacts")
            logs_dir = Path("logs")

            artifacts_dir.mkdir(exist_ok=True)
            logs_dir.mkdir(exist_ok=True)

            # Test write permissions
            test_file = artifacts_dir / ".preflight_test"
            test_file.write_text("test")
            test_file.unlink()

            checks_passed += 1
            results["checks"]["directories"] = {
                "status": "PASS",
                "message": "Directories writable",
            }
            if verbose:
                console.print("[green]✓ Required directories writable[/green]")
        except Exception as e:
            results["checks"]["directories"] = {"status": "FAIL", "message": str(e)}
            results["errors"].append(f"Directory access: {e}")
            if verbose:
                console.print(f"[red]✗ Directory access failed: {e}[/red]")

        # Determine overall status
        if checks_passed == total_checks:
            results["status"] = "HEALTHY"
            overall_status = "[green]HEALTHY[/green]"
        elif checks_passed > 0:
            results["status"] = "DEGRADED"
            overall_status = "[yellow]DEGRADED[/yellow]"
        else:
            results["status"] = "UNHEALTHY"
            overall_status = "[red]UNHEALTHY[/red]"

        results["summary"] = {
            "checks_passed": checks_passed,
            "total_checks": total_checks,
            "pass_rate": checks_passed / total_checks if total_checks > 0 else 0,
        }

        if json_output:
            console.print(jsonlib.dumps(results, indent=2))
        else:
            console.print(f"\n[bold]Preflight Status:[/bold] {overall_status}")
            console.print(f"Passed: {checks_passed}/{total_checks} checks")

            if results["errors"] and verbose:
                console.print("\n[bold red]Errors:[/bold red]")
                for error in results["errors"]:
                    console.print(f"  • {error}")

        # Exit with non-zero code if not healthy in strict mode
        if strict and results["status"] != "HEALTHY":
            raise typer.Exit(code=1)

    except ImportError as e:
        console.print(f"[red]Preflight check failed - missing dependencies: {e}[/red]")
        raise typer.Exit(code=1)


def main():
    """Main entry point for the CLI orchestrator."""
    app()


if __name__ == "__main__":
    main()
