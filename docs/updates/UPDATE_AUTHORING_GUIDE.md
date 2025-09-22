# Update Authoring Template and Guide

This guide explains how to create standardized plan updates for the `DICKY1987/cli_multi_rapid_DEV` repository.

## Template

Start from `updates/UPDATE_TEMPLATE.json`. Replace placeholders and keep the structure compatible with the schema:

- `$schema`: `.ai/schemas/plan_update.schema.json`
- `update_id`: timestamped, unique (e.g., `2025-09-21T1330_code_quality`)
- `metadata`: author, created, short description
- `deliverables[]`: the concrete outputs expected after the update is applied
- `acceptance_criteria[]`: machine-checkable assertions defining success
- `operations[]`: how to realize the change (e.g., add or update module ops)

## Deliverables

Always declare deliverables for visibility and verification.

Example (file deliverable):

```json
{
  "id": "doc.plan_updates",
  "type": "file",
  "title": "Plan Updates Guide",
  "path": "docs/plan-updates.md",
  "must_exist": true,
  "must_contain": ["Plan Updates Workflow"]
}
```

Notes:
- `expected_sha256` is optional; when your write_file ops include base64 content, the update tooling auto-fills this in the deliverables manifest.
- Other deliverable types: `report`, `patch`, `summary`, `log`, `artifact_bundle`, `url`.

## Acceptance Criteria

Add criteria to codify success. Supported kinds include:

- `assert_contains`: ensure a file contains specific tokens
- `assert_not_contains`: ensure a file does not contain tokens
- `file_checksum`: lock a file to an exact hash

Example:

```json
{ "type": "assert_contains", "file": "docs/plan-updates.md", "must_contain": ["module-based updates"] }
```

## Operations

Use operations to realize the update. Common operations:

- `add_module`: add a brand-new module JSON to `.ai/plan_modules/`
- `upsert_ops`: append/prepend new ops into an existing module
- `replace_ops` and `remove_ops`: surgically refine module content using selectors
- `set_metadata`, `set_defaults`, `set_execution`: patch top-level plan configuration
- `set_paths`: set allow/deny path lists used during apply
- `update_manifest`: control module ordering

Example (write a docs file via `upsert_ops`):

```json
{
  "type": "upsert_ops",
  "module": "40-files-docs.json",
  "strategy": "append",
  "ops": [
    {
      "op": "write_file",
      "path": "docs/plan-updates.md",
      "content_base64": "<base64-of-your-content>",
      "if_exists": "skip",
      "phase": "apply",
      "dry_run_effect": "noop"
    }
  ]
}
```

Tip: generate base64 easily:

- PowerShell: `[Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes((Get-Content -Raw .\file.md)))`
- Python: `python - <<<'import base64,sys;print(base64.b64encode(open(sys.argv[1],"rb").read()).decode())' file.md`

## Workflow

1) Apply the update package (emits deliverables manifest)

```
task plan:update UPDATE=updates/<your_update>.json
```

2) Compose the plan (fingerprint, summary)

```
task plan:compose
```

3) Validate plan (dry-run, validate phase)

```
task plan:validate
```

4) Shadow-apply (safe preview of writes)

```
task plan:shadow-apply
```

5) Validate deliverables manifest

```
task plan:validate-deliverables MANIFEST=artifacts/updates/<update_id>/deliverables.manifest.json
```

6) Apply for real (apply phase)

```
task plan:apply
```

## Selectors (for replace/remove)

Use selectors to target ops precisely:

- `write_file_path`: `{ "kind": "write_file_path", "path": "docs/plan-updates.md" }`
- `file`: `{ "kind": "file", "file": "<path for non-write ops>" }`
- `op_type`: `{ "kind": "op_type", "op": "write_file" }`
- `regex`: `{ "kind": "regex", "field": "path", "pattern": "^docs/.*\\.md$" }`

## Best Practices

- Keep updates small, focused, and idempotent
- Always specify deliverables and acceptance criteria
- Prefer `if_exists: "skip"` with checksums for write safety
- Use `replace_section` with unique anchors and idempotency markers
- Constrain writes with path allow/deny lists when composing/applying
