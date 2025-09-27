#!/usr/bin/env python3
"""
CLI Orchestrator Main Entry Point

Provides the main command-line interface for the deterministic, schema-driven
CLI orchestrator that routes between deterministic tools and AI agents.
"""

import sys
from pathlib import Path
from typing import Optional, List, Dict, Any

import typer
from rich.console import Console
from rich.table import Table

app = typer.Typer(
    name="cli-orchestrator",
    help="Deterministic, Schema-Driven CLI Orchestrator",
    rich_markup_mode="rich",
)
console = Console()


# Cross-platform safe success/failure symbols (avoid Unicode on legacy Windows)
def _symbol(ok: bool) -> str:
    enc = (getattr(sys.stdout, "encoding", None) or "").lower()
    if "utf" in enc:
        return "✓" if ok else "✗"
    return "OK" if ok else "FAIL"


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
            console.print(f"[green]{_symbol(True)} Workflow completed successfully[/green]")
        else:
            console.print(f"[red]{_symbol(False)} Workflow failed: {result.error}[/red]")
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
            console.print(f"[green]{_symbol(True)} Artifact is valid[/green]")
        else:
            console.print(f"[red]{_symbol(False)} Artifact validation failed[/red]")
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


@app.command("run-ipt-wt")
def run_ipt_wt(
    workflow_file: Path = typer.Argument(
        Path(".ai/workflows/ipt_wt_workflow.yaml"), help="Path to IPT/WT workflow YAML"
    ),
    request: Optional[str] = typer.Option(None, "--request", help="User request/brief"),
    budget: Optional[int] = typer.Option(
        None, "--budget", help="Budget remaining (token estimate)"
    ),
):
    """Run the IPT/WT workflow scaffolding with budget-aware routing.

    Produces an artifact at artifacts/ipt-wt/decision.json documenting the routing decision.
    """
    console.print(f"[bold blue]Running IPT/WT workflow:[/bold blue] {workflow_file}")
    try:
        from .workflow_runner import WorkflowRunner

        runner = WorkflowRunner()
        result = runner.run_ipt_wt_workflow(workflow_file=workflow_file, request=request, budget=budget)
        if result.success:
            console.print("[green]IPT/WT workflow completed successfully[/green]")
            if result.artifacts:
                console.print(f"[dim]Artifacts: {', '.join(result.artifacts)}[/dim]")
        else:
            console.print(f"[red]IPT/WT workflow failed: {result.error}[/red]")
            raise typer.Exit(code=1)
    except ImportError:
        console.print("[red]Workflow runner not available[/red]")
        raise typer.Exit(code=1)


# Coordination command group
coordination_app = typer.Typer(
    name="coordination", help="Multi-agent workflow coordination commands"
)
app.add_typer(coordination_app, name="coordination")


def _ensure_state_dir() -> Path:
    state_dir = Path("state/coordination")
    state_dir.mkdir(parents=True, exist_ok=True)
    return state_dir


def _json_default(o: Any):
    try:
        import enum

        if isinstance(o, enum.Enum):
            return o.value
    except Exception:
        pass
    try:
        from dataclasses import asdict, is_dataclass

        if is_dataclass(o):
            return asdict(o)
    except Exception:
        pass
    if isinstance(o, (Path,)):
        return str(o)
    return str(o)


@coordination_app.command("run")
def coordination_run(
    workflows: List[Path] = typer.Argument(
        ..., help="Workflow YAML files to coordinate"
    ),
    mode: str = typer.Option("parallel", "--mode", help="Coordination mode"),
    max_parallel: int = typer.Option(3, "--max-parallel", help="Max parallel workflows"),
    budget: float = typer.Option(50.0, "--budget", help="Total budget in USD"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Show plan without executing"),
):
    """Run coordinated multi-workflow execution."""
    console.print("[bold blue]Running coordinated workflows[/bold blue]")
    console.print(f"[dim]Mode={mode}, MaxParallel={max_parallel}, Budget=${budget:.2f}, DryRun={dry_run}[/dim]")

    try:
        # Load defaults from coordination config (override only if still defaults)
        from .config.coordination import load_coordination_config

        cfg = load_coordination_config()
        # If user did not change defaults, adopt config values
        if mode == "parallel" and cfg.default_mode:
            mode = cfg.default_mode
        if max_parallel == 3 and cfg.max_parallel_workflows:
            max_parallel = cfg.max_parallel_workflows
        if abs(budget - 50.0) < 1e-9 and cfg.default_budget:
            budget = cfg.default_budget

        from .workflow_runner import WorkflowRunner

        runner = WorkflowRunner()
        result = runner.run_coordinated_workflows(
            workflow_files=workflows,
            coordination_mode=mode,
            max_parallel=max_parallel,
            total_budget=budget,
            dry_run=dry_run,
        )

        state_dir = _ensure_state_dir()
        summary = {
            "coordination_id": result.coordination_id,
            "success": result.success,
            "total_tokens_used": result.total_tokens_used,
            "total_execution_time": result.total_execution_time,
            "parallel_efficiency": result.parallel_efficiency,
            "conflicts_detected": result.conflicts_detected,
            "workflows": {
                name: {
                    "success": r.success,
                    "tokens_used": r.tokens_used,
                    "steps_completed": r.steps_completed,
                    "execution_time": r.execution_time,
                    "error": r.error,
                    "artifacts": r.artifacts,
                }
                for name, r in (result.workflow_results or {}).items()
            },
            "params": {
                "mode": mode,
                "max_parallel": max_parallel,
                "budget": budget,
                "dry_run": dry_run,
                "input_files": [str(p) for p in workflows],
            },
        }

        out_path = state_dir / f"{result.coordination_id}.json"
        try:
            import json

            with out_path.open("w", encoding="utf-8") as f:
                json.dump(summary, f, indent=2, default=_json_default)
            console.print(f"[dim]Saved state: {out_path}[/dim]")
        except Exception as e:
            console.print(f"[yellow]Could not persist coordination state: {e}[/yellow]")

        if result.success:
            console.print(f"[green]{_symbol(True)} Coordination completed: {result.coordination_id}[/green]")
        else:
            if result.conflicts_detected:
                for c in result.conflicts_detected:
                    console.print(f"[red]- {c}[/red]")
            console.print(f"[red]{_symbol(False)} Coordination failed: {result.coordination_id}[/red]")
            raise typer.Exit(code=1)

    except ImportError:
        console.print("[red]Workflow runner not available[/red]")
        raise typer.Exit(code=1)


@coordination_app.command("plan")
def coordination_plan(
    workflows: List[Path] = typer.Argument(..., help="Workflow files to analyze"),
    output: Path = typer.Option(
        Path("coordination_plan.json"), "--output", help="Output file"
    ),
):
    """Create coordination plan with conflict detection."""
    try:
        import json
        import yaml
        from dataclasses import asdict
        from .coordination import WorkflowCoordinator

        # Load workflows
        loaded: List[Dict[str, Any]] = []
        for wf in workflows:
            with wf.open("r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
                loaded.append(data)

        coordinator = WorkflowCoordinator()
        plan = coordinator.create_coordination_plan(loaded)

        # Serialize plan safely (convert Enums)
        def _enum_safe(obj: Any) -> Any:
            d = asdict(obj)
            # Best-effort enum conversion
            def _fix(v):
                try:
                    import enum

                    if isinstance(v, enum.Enum):
                        return v.value
                except Exception:
                    pass
                return v

            for k, v in list(d.items()):
                if isinstance(v, list):
                    d[k] = [(_fix(x) if not isinstance(x, dict) else x) for x in v]
                else:
                    d[k] = _fix(v)
            return d

        plan_dict = _enum_safe(plan)
        with output.open("w", encoding="utf-8") as f:
            json.dump(plan_dict, f, indent=2, default=_json_default)
        console.print(f"[green]{_symbol(True)} Plan written to {output}[/green]")
    except Exception as e:
        console.print(f"[red]{_symbol(False)} Failed to create plan: {e}[/red]")
        raise typer.Exit(code=1)


@coordination_app.command("status")
def coordination_status(
    coordination_id: str = typer.Argument(..., help="Coordination session ID"),
):
    """Show coordination session status from persisted state."""
    try:
        import json

        state_file = _ensure_state_dir() / f"{coordination_id}.json"
        if not state_file.exists():
            console.print(f"[yellow]No state found for {coordination_id}[/yellow]")
            raise typer.Exit(code=1)

        with state_file.open("r", encoding="utf-8") as f:
            state = json.load(f)

        ok = bool(state.get("success"))
        console.print(
            f"[bold blue]Coordination {coordination_id}[/bold blue] - {'SUCCESS' if ok else 'FAILED'}"
        )
        console.print(
            f"[dim]tokens={state.get('total_tokens_used', 0)}, time={state.get('total_execution_time', 0.0):.2f}s, efficiency={state.get('parallel_efficiency', 0.0):.2f}[/dim]"
        )

        conflicts = state.get("conflicts_detected") or []
        if conflicts:
            console.print("[red]Conflicts detected:[/red]")
            for c in conflicts:
                console.print(f"[red]- {c}[/red]")

    except Exception as e:
        console.print(f"[red]Error reading status: {e}[/red]")
        raise typer.Exit(code=1)


@coordination_app.command("cancel")
def coordination_cancel(
    coordination_id: str = typer.Argument(..., help="Coordination session ID"),
):
    """Cancel a running coordination session (cooperative)."""
    try:
        cancel_flag = _ensure_state_dir() / f"{coordination_id}.cancel"
        cancel_flag.touch(exist_ok=True)
        console.print(f"[yellow]Cancel flag written: {cancel_flag}[/yellow]")
    except Exception as e:
        console.print(f"[red]Failed to write cancel flag: {e}[/red]")
        raise typer.Exit(code=1)


@coordination_app.command("dashboard")
def coordination_dashboard(
    coordination_id: Optional[str] = typer.Option(
        None, "--id", help="Specific coordination ID"
    ),
    refresh_seconds: int = typer.Option(5, "--refresh", help="Refresh interval seconds"),
    iterations: int = typer.Option(0, "--iterations", help="Stop after N iterations (0=run)"),
):
    """Show a simple real-time dashboard from persisted state."""
    try:
        import json
        import time
        from rich.live import Live

        state_dir = _ensure_state_dir()

        def _latest_id() -> Optional[str]:
            files = sorted(state_dir.glob("coord_*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
            return files[0].stem if files else None

        coord_id = coordination_id or _latest_id()
        if not coord_id:
            console.print("[yellow]No coordination sessions found[/yellow]")
            return

        state_file = state_dir / f"{coord_id}.json"
        if not state_file.exists():
            console.print(f"[yellow]No state found for {coord_id}[/yellow]")
            raise typer.Exit(code=1)

        def render() -> Table:
            table = Table(title=f"Coordination Dashboard - {coord_id}")
            table.add_column("Workflow", style="cyan")
            table.add_column("Success", style="green")
            table.add_column("Tokens", style="magenta")
            table.add_column("Steps", style="yellow")
            table.add_column("Time (s)", style="blue")
            table.add_column("Error", style="red")

            try:
                with state_file.open("r", encoding="utf-8") as f:
                    state = json.load(f)
            except Exception:
                state = {}

            workflows = (state.get("workflow_results") or {})
            for name, w in workflows.items():
                table.add_row(
                    name,
                    str(w.get("success")),
                    str(w.get("tokens_used", 0)),
                    str(w.get("steps_completed", 0)),
                    f"{(w.get('execution_time') or 0.0):.2f}",
                    (w.get("error") or ""),
                )

            return table

        loops = 0
        with Live(render(), refresh_per_second=4) as live:
            while iterations <= 0 or loops < iterations:
                time.sleep(max(refresh_seconds, 1))
                live.update(render())
                loops += 1

    except Exception as e:
        console.print(f"[red]Dashboard error: {e}[/red]")
        raise typer.Exit(code=1)


@coordination_app.command("report")
def coordination_report(
    coordination_id: str = typer.Argument(..., help="Coordination session ID"),
    format: str = typer.Option("json", "--format", help="Report format (json/html/csv)"),
    output: Optional[Path] = typer.Option(
        None, "--output", help="Output file (defaults to artifacts/reports)"
    ),
):
    """Generate a simple coordination report."""
    try:
        import json
        import csv

        state_file = _ensure_state_dir() / f"{coordination_id}.json"
        if not state_file.exists():
            console.print(f"[yellow]No state found for {coordination_id}[/yellow]")
            raise typer.Exit(code=1)

        with state_file.open("r", encoding="utf-8") as f:
            state = json.load(f)

        out_dir = Path("artifacts/reports")
        out_dir.mkdir(parents=True, exist_ok=True)
        fmt = format.lower()
        out_path = output or out_dir / f"{coordination_id}.{fmt}"

        if fmt == "json":
            with out_path.open("w", encoding="utf-8") as f:
                json.dump(state, f, indent=2, default=_json_default)
        elif fmt == "csv":
            with out_path.open("w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(["workflow", "success", "tokens_used", "steps_completed", "execution_time", "error"])
                for name, w in (state.get("workflow_results") or {}).items():
                    writer.writerow([
                        name,
                        w.get("success"),
                        w.get("tokens_used", 0),
                        w.get("steps_completed", 0),
                        w.get("execution_time", 0.0),
                        (w.get("error") or ""),
                    ])
        elif fmt == "html":
            rows = []
            for name, w in (state.get("workflow_results") or {}).items():
                rows.append(
                    f"<tr><td>{name}</td><td>{w.get('success')}</td><td>{w.get('tokens_used',0)}</td><td>{w.get('steps_completed',0)}</td><td>{w.get('execution_time',0.0)}</td><td>{(w.get('error') or '')}</td></tr>"
                )
            html = f"""
<!doctype html>
<html><head><meta charset='utf-8'><title>{coordination_id} Report</title>
<style>table{{border-collapse:collapse}}td,th{{border:1px solid #ccc;padding:4px}}</style></head>
<body>
<h1>Coordination Report - {coordination_id}</h1>
<p>Status: {'SUCCESS' if state.get('success') else 'FAILED'}</p>
<p>Tokens: {state.get('total_tokens_used',0)} | Time: {state.get('total_execution_time',0.0)}s | Efficiency: {state.get('parallel_efficiency',0.0):.2f}</p>
<table><thead><tr><th>Workflow</th><th>Success</th><th>Tokens</th><th>Steps</th><th>Time(s)</th><th>Error</th></tr></thead>
<tbody>
{''.join(rows)}
</tbody></table>
</body></html>
"""
            with out_path.open("w", encoding="utf-8") as f:
                f.write(html)
        else:
            console.print(f"[red]Unknown format: {format}[/red]")
            raise typer.Exit(code=1)

        console.print(f"[green]{_symbol(True)} Report written to {out_path}[/green]")
    except Exception as e:
        console.print(f"[red]Report error: {e}[/red]")
        raise typer.Exit(code=1)


@coordination_app.command("history")
def coordination_history(
    days: int = typer.Option(7, "--days", help="Days of history to show"),
    workflow_filter: Optional[str] = typer.Option(None, "--workflow", help="Filter by workflow name contains"),
):
    """Show recent coordination sessions from persisted state."""
    try:
        import json
        import time

        since = time.time() - days * 24 * 3600
        state_dir = _ensure_state_dir()
        files = sorted(state_dir.glob("coord_*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
        shown = 0
        for f in files:
            if f.stat().st_mtime < since:
                continue
            with f.open("r", encoding="utf-8") as fh:
                state = json.load(fh)

            if workflow_filter:
                wfs = state.get("workflow_results") or {}
                if not any(workflow_filter.lower() in name.lower() for name in wfs.keys()):
                    continue

            status = "SUCCESS" if state.get("success") else "FAILED"
            console.print(f"{f.stem}  {status}  tokens={state.get('total_tokens_used',0)} time={state.get('total_execution_time',0.0):.2f}s")
            shown += 1

        if shown == 0:
            console.print("[yellow]No sessions found in the requested window[/yellow]")
    except Exception as e:
        console.print(f"[red]History error: {e}[/red]")
        raise typer.Exit(code=1)

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
            status = _symbol(probe.ok)
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
                console.print(f"{_symbol(True)} {name}: {probe.version}")
            else:
                console.print(f"{_symbol(False)} {name}: not available")

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
            ok = result.code == 0
            status = f"{_symbol(ok)} {'PASS' if ok else 'FAIL'}"
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
            console.print(f"[green]{_symbol(True)} Containers started successfully[/green]")
        else:
            console.print(f"[red]{_symbol(False)} Failed to start containers: {result.stderr}[/red]")
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
            console.print(f"[green]{_symbol(True)} Containers stopped successfully[/green]")
        else:
            console.print(f"[red]{_symbol(False)} Failed to stop containers: {result.stderr}[/red]")
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
            console.print(f"[red]{_symbol(False)} Failed to list containers: {result.stderr}[/red]")
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
            console.print(f"[green]{_symbol(True)} Repository cloned successfully[/green]")
        else:
            console.print(f"[red]{_symbol(False)} Failed to clone repository: {result.stderr}[/red]")
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
            console.print(f"[red]{_symbol(False)} Failed to get status: {result.stderr}[/red]")
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
            console.print(f"[green]{_symbol(True)} Pull request created successfully[/green]")
            console.print(result.stdout)
        else:
            console.print(f"[red]{_symbol(False)} Failed to create PR: {result.stderr}[/red]")
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
