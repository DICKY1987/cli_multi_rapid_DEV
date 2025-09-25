# AI Edit Pipeline — Quickstart

## Install (local)

```
pip install jsonschema
```

## Author a Plan
- Generate a plan using your AI planner.
- Save to `artifacts/edit_plan.json`.

## Validate

```
python tools/edit_validator_v2.py artifacts/edit_plan.json
```

## Apply

```
python tools/apply_edits.py artifacts/edit_plan.json
```

## CI
Pull requests containing `edit_plan*.json` or `artifacts/*.json` are auto-validated by `.github/workflows/ai_edit_validation.yml`.
