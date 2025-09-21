import json
from pathlib import Path

import pytest

from cli_multi_rapid.verifier import Verifier


def write_json(path: Path, data: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


@pytest.fixture()
def verifier() -> Verifier:
    return Verifier()


def test_verify_artifact_basic_pass_and_fail(tmp_path: Path, verifier: Verifier) -> None:
    # Valid artifact for basic validation
    valid = {"timestamp": "2025-09-21T00:00:00Z", "type": "unit-test"}
    valid_path = write_json(tmp_path / "artifact.json", valid)

    assert verifier.verify_artifact(valid_path) is True

    # Missing required field should fail
    invalid = {"type": "unit-test"}
    invalid_path = write_json(tmp_path / "artifact_bad.json", invalid)
    assert verifier.verify_artifact(invalid_path) is False


def test_verify_artifact_with_schema(tmp_path: Path, verifier: Verifier) -> None:
    artifact = {"timestamp": "2025-09-21T00:00:00Z", "type": "ok", "extra": 1}
    schema = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "type": "object",
        "required": ["timestamp", "type"],
        "properties": {
            "timestamp": {"type": "string"},
            "type": {"type": "string"},
            "extra": {"type": "number"},
        },
        "additionalProperties": True,
    }

    artifact_path = write_json(tmp_path / "artifact.json", artifact)
    schema_path = write_json(tmp_path / "schema.json", schema)

    assert verifier.verify_artifact(artifact_path, schema_path) is True

    # Make it invalid against the schema
    bad_artifact = {"timestamp": 123, "type": "ok"}
    bad_artifact_path = write_json(tmp_path / "artifact_bad.json", bad_artifact)
    assert verifier.verify_artifact(bad_artifact_path, schema_path) is False
