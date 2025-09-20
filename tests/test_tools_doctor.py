import json
from types import SimpleNamespace

import cli_multi_rapid.cli as cli


class DummyCompleted:
    def __init__(self, code: int, out: str = "", err: str = ""):
        self.code = code
        self.stdout = out
        self.stderr = err
        self.duration_s = 0.01
        self.argv = []


def test_tools_doctor_parses_and_prints(monkeypatch, capsys):
    # Patch detection to return all ok
    def fake_detect_all(_runner):
        Probe = SimpleNamespace
        return {
            "git": Probe(ok=True, version="2.46.0", path="git", details=None),
            "docker": Probe(ok=True, version="27.0.0", path="docker", details=None),
            "ruff": Probe(ok=True, version="0.5.6", path="ruff", details=None),
        }

    monkeypatch.setenv("PYTHONPATH", ".")
    import integrations.registry_tools as reg

    monkeypatch.setattr(reg, "detect_all", fake_detect_all)

    code = cli.main(["tools", "doctor"])
    captured = capsys.readouterr().out
    data = json.loads(captured)
    assert code == 0
    assert data["git"]["ok"] is True
    assert "version" in data["ruff"]

