import json

import cli_multi_rapid.cli as cli


class DummyRes:
    def __init__(self, code=0, duration_s=0.01):
        self.code = code
        self.duration_s = duration_s


def test_quality_run_aggregates(monkeypatch, capsys):
    class DummySuite:
        def __init__(self, _runner):
            pass

        def run_all(self, fix=False):  # noqa: ARG002
            return {
                "ruff": DummyRes(0),
                "mypy": DummyRes(0),
                "bandit": DummyRes(0),
                "semgrep": DummyRes(0),
            }

    import integrations.python_quality as q

    monkeypatch.setattr(q, "QualitySuite", DummySuite)
    code = cli.main(["quality", "run"])  # should return 0
    out = capsys.readouterr().out
    data = json.loads(out)
    assert code == 0
    assert set(data.keys()) == {"ruff", "mypy", "bandit", "semgrep"}

