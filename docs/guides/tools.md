Tool Integration Guide

- Config file: `config/tools.yaml` (schema: `.ai/schemas/tools.schema.json`).
- Override config path: set env `CLI_MR_TOOLS_CONFIG` to a YAML file.
- Selection precedence: env override path > `config/tools.yaml` > PATH auto-detect.

Commands

- `cli-multi-rapid tools doctor` — show versions and pass/fail for known tools.
- `cli-multi-rapid quality run [--fix]` — run ruff, mypy, bandit, semgrep.
- `cli-multi-rapid containers up|down` — docker compose via `config/docker-compose.yml`.

Windows Notes

- Prefer explicit binaries (`git.exe`, `gh.exe`, `docker.exe`, `code.cmd`, `node.exe`, `npx.cmd`).
- If PowerShell policy blocks scripts, use `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`.

