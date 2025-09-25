# CLI Orchestrator

![CI](https://github.com/DICKY1987/cli_multi_rapid_DEV/actions/workflows/ci.yml/badge.svg)
![Coverage](https://img.shields.io/badge/coverage-80%25%2B-brightgreen)

**CLI Orchestrator** is a deterministic, schema-driven CLI orchestrator that stitches together multiple developer tools and AI agents into predefined, auditable workflows. It prioritizes scripts first, escalates to AI only where judgment is required, and emits machine-readable artifacts with gates and verification at every hop.

The platform is designed for developers who need reliable, cost-aware automation in their development workflows.

## Quick start

You can run the CLI orchestrator directly with the Python interpreter without any
installation steps. The examples below assume you are executing commands in
the repository root.

```bash
# Run a workflow with dry-run
cli-orchestrator run .ai/workflows/PY_EDIT_TRIAGE.yaml --files "src/**/*.py" --lane lane/ai-coding/fix-imports --dry-run

# Execute workflow
cli-orchestrator run .ai/workflows/PY_EDIT_TRIAGE.yaml --files "src/**/*.py"

# Verify an artifact against schema
cli-orchestrator verify artifacts/diagnostics.json --schema .ai/schemas/diagnostics.schema.json
```

If you prefer to install the package into your current environment, you can
use a local editable install via `pip`. This step is optional and not
required to run the examples above:

```bash
pip install -e .
cli-orchestrator run .ai/workflows/CODE_QUALITY.yaml
```

The editable install will register a console script entry point named
`cli-orchestrator`. This provides access to all workflow orchestration functionality through
a unified command-line interface.

## Core Features

The CLI Orchestrator provides comprehensive workflow automation:

**Core Orchestration:**
- Schema-validated YAML workflow definitions
- Deterministic tool execution with AI escalation
- Cost tracking and budget enforcement
- Machine-readable artifact generation

**Architecture & Development:**
- **Single Main Branch**: Simplified development flow with `main` as the sole source of truth
- Clean, consolidated codebase with all features merged
- Automated CI/CD with comprehensive testing
- Comprehensive GitHub integration for repository management
**Adapter Framework:**
- Unified interface for tools and AI services
- Router system for step execution
- Gate system for verification and quality control
- Comprehensive GitHub integration and repository management

**Command Examples:**
```bash
# Workflow operations
cli-orchestrator run .ai/workflows/PY_EDIT_TRIAGE.yaml --files "src/**/*.py"
cli-orchestrator run .ai/workflows/CODE_QUALITY.yaml --dry-run

# Verification and validation
cli-orchestrator verify artifacts/diagnostics.json --schema .ai/schemas/diagnostics.schema.json
cli-orchestrator cost report --last-run

# GitHub integration
cli-orchestrator run .ai/workflows/GITHUB_REPO_ANALYSIS.yaml --repo owner/repo
cli-orchestrator run .ai/workflows/GITHUB_ISSUE_AUTOMATION.yaml --repo owner/repo
```

## Architecture Overview

The CLI Orchestrator follows a modular architecture designed for reliability and maintainability:

**Core Components:**
- `src/cli_multi_rapid/` - Core orchestrator implementation with workflow runner and router
- `.ai/workflows/` - YAML workflow definitions (schema-validated)
- `.ai/schemas/` - JSON Schema definitions for validation
- `adapters/` - Tool and AI adapter implementations
- `artifacts/` - Workflow execution artifacts (patches, reports)

**Key Modules:**
- **Workflow Runner**: Executes schema-validated YAML workflows
- **Router System**: Routes steps between deterministic tools and AI adapters
- **Adapter Framework**: Unified interface for tools and AI services
- **Cost Tracker**: Token usage and budget enforcement
- **Gate System**: Verification and quality gates

## Development & Branch Structure

**Simplified Branch Model:**
- **Single `main` branch**: All development happens on the main branch
- **Clean history**: Repository consolidated from multiple development branches
- **Feature development**: Use short-lived feature branches that merge to main quickly
- **No long-running branches**: Eliminates complexity and merge conflicts

**Repository Organization:**
- Tool registry: define tools in `config/tools.yaml`
- Workflow definitions: `.ai/workflows/*.yaml` (schema-validated)
- Adapters: `src/cli_multi_rapid/adapters/` for tool integrations
- Schemas: `.ai/schemas/` for validation and artifact structure

Hooks setup

- Configure Git to use bundled hooks (merge-safety, optional license gate):
  - POSIX: `bash scripts/install_hooks.sh`
  - PowerShell: `./scripts/install_hooks.ps1`

## Development guide

Development workflows emphasise high code quality, reproducibility and clear
communication. The repository includes a commit message template
(`.gitmessage.txt`) and a sample CI workflow (`.github/workflows/ci.yml`)
that installs common development tools such as `pre-commit`, `ruff` and
`pytest`. Although these tools may not be available in all environments,
they are preconfigured so that continuous integration (CI) pipelines can
enforce formatting, linting, static type checking and unit test execution.

To run the test suite locally using the built‑in Python `unittest` runner:

```bash
python -m unittest discover -s tests -v
```

## Cost Reports

- Emit tokens locally: `powershell -NoProfile -File scripts/emit_tokens.ps1 -Out artifacts/tokens.json`
- Generate report: `powershell -NoProfile -File scripts/report_costs.ps1 -OutDir artifacts/cost`
- CI: uploads cost artifacts and posts a PR summary; a scheduled budget check runs daily.

Alternatively, if you have `pytest` available, you can benefit from its
more expressive output and coverage reporting:

```bash
pytest -q --cov=src --cov-report=term-missing --cov-fail-under=80
```

## Repository structure

| Path                       | Purpose                                                 |
|---------------------------|---------------------------------------------------------|
| `src/cli_multi_rapid/`     | Core orchestrator implementation with workflow runner   |
| `.ai/workflows/`           | YAML workflow definitions (schema-validated)            |
| `.ai/schemas/`             | JSON Schema definitions for validation                   |
| `adapters/`                | Tool and AI adapter implementations                      |
| `artifacts/`               | Workflow execution artifacts (patches, reports)         |
| `tests/`                   | Comprehensive unit and integration tests                 |
| `config/`                  | System configuration files (YAML, JSON schemas)         |
| `scripts/`                 | Setup, deployment, and utility scripts                  |
| `docs/`                    | CLI Orchestrator documentation                           |
| `cost/`                    | Token usage tracking and budget reports                 |
| `.github/workflows`        | CI/CD pipelines for automated testing and deployment    |

## Contributing

Contributions are welcome! Feel free to open issues or pull requests to
discuss improvements, report bugs, or suggest new features. Please follow the
commit message guidelines defined in `.gitmessage.txt` and aim to include
tests for any new functionality.

## VS Code

See `VSCODE_SETUP.md` for available tasks, debug configurations, and how to optionally merge the Codex configuration package from `CODEX_IMPLEMENTATION/vscode_configuration/` into `.vscode` with a backup.
