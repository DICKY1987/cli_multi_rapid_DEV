"""Pre-commit hooks adapter."""

from __future__ import annotations

from .process import CommandResult, ProcessRunner
from .registry import get_selected_tool_path
from .tools_base import PreCommit, ToolProbe


class PreCommitAdapter:
    """Pre-commit hooks adapter."""

    def __init__(self, runner: ProcessRunner) -> None:
        self.runner = runner
        self.binary = get_selected_tool_path("pre-commit", "precommit")

    def version(self) -> ToolProbe:
        """Get pre-commit version information."""
        try:
            res = self.runner.run([self.binary, "--version"])
            # Extract version from output like "pre-commit 3.4.0"
            version = None
            if res.stdout:
                parts = res.stdout.strip().split()
                if len(parts) >= 2:
                    version = parts[1]

            return ToolProbe(
                name="pre-commit",
                path=self.binary,
                version=version,
                ok=res.code == 0,
                details=res.stderr if res.code != 0 else None,
            )
        except Exception as e:
            return ToolProbe(
                name="pre-commit",
                path=None,
                version=None,
                ok=False,
                details=str(e),
            )

    def install(self) -> CommandResult:
        """Install pre-commit hooks."""
        return self.runner.run([self.binary, "install"])

    def run_all(self) -> CommandResult:
        """Run all pre-commit hooks."""
        return self.runner.run([self.binary, "run", "--all-files"])

    def autoupdate(self) -> CommandResult:
        """Update pre-commit hook versions."""
        return self.runner.run([self.binary, "autoupdate"])

    def run_hook(self, hook_id: str) -> CommandResult:
        """Run a specific pre-commit hook."""
        return self.runner.run([self.binary, "run", hook_id])

    def uninstall(self) -> CommandResult:
        """Uninstall pre-commit hooks."""
        return self.runner.run([self.binary, "uninstall"])

    def clean(self) -> CommandResult:
        """Clean pre-commit cache."""
        return self.runner.run([self.binary, "clean"])

    def validate_config(self) -> CommandResult:
        """Validate .pre-commit-config.yaml."""
        return self.runner.run([self.binary, "validate-config"])

    def validate_manifest(self) -> CommandResult:
        """Validate .pre-commit-hooks.yaml."""
        return self.runner.run([self.binary, "validate-manifest"])

    def sample_config(self) -> CommandResult:
        """Generate a sample .pre-commit-config.yaml."""
        return self.runner.run([self.binary, "sample-config"])


def create_precommit_adapter(runner: ProcessRunner) -> PreCommit:
    """Factory function to create pre-commit adapter."""
    return PreCommitAdapter(runner)
