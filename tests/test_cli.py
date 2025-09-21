from typer.testing import CliRunner

from cli_multi_rapid.cli_app import app


def test_cli_help_runs():
    runner = CliRunner()
    result = runner.invoke(app, ["--help"])  # just ensure CLI is wired
    assert result.exit_code == 0
    assert "Deterministic" in result.stdout or result.stdout  # any output
