"""Version Control System adapters."""

from __future__ import annotations

from typing import Optional

from .process import CommandResult, ProcessRunner
from .registry import get_selected_tool_path
from .tools_base import VCS, ToolProbe


class GitAdapter:
    """Git version control adapter."""

    def __init__(self, runner: ProcessRunner) -> None:
        self.runner = runner
        self.binary = get_selected_tool_path("git", "vcs")

    def version(self) -> ToolProbe:
        """Get Git version information."""
        try:
            res = self.runner.run([self.binary, "--version"])
            # Extract version from output like "git version 2.42.0"
            version = None
            if res.stdout:
                parts = res.stdout.strip().split()
                if len(parts) >= 3:
                    version = parts[2]

            return ToolProbe(
                name="git",
                path=self.binary,
                version=version,
                ok=res.code == 0,
                details=res.stderr if res.code != 0 else None,
            )
        except Exception as e:
            return ToolProbe(
                name="git",
                path=None,
                version=None,
                ok=False,
                details=str(e),
            )

    def clone(self, url: str, target_dir: str) -> CommandResult:
        """Clone a repository."""
        return self.runner.run([self.binary, "clone", url, target_dir])

    def status(self, cwd: Optional[str] = None) -> CommandResult:
        """Get repository status."""
        return self.runner.run([self.binary, "status", "--porcelain"], cwd=cwd)

    def checkout(self, branch: str, cwd: Optional[str] = None) -> CommandResult:
        """Checkout a branch."""
        return self.runner.run([self.binary, "checkout", branch], cwd=cwd)

    def fetch(self, cwd: Optional[str] = None) -> CommandResult:
        """Fetch from remote."""
        return self.runner.run([self.binary, "fetch"], cwd=cwd)

    def add(self, files: str = ".", cwd: Optional[str] = None) -> CommandResult:
        """Add files to staging."""
        return self.runner.run([self.binary, "add", files], cwd=cwd)

    def commit(self, message: str, cwd: Optional[str] = None) -> CommandResult:
        """Create a commit."""
        return self.runner.run([self.binary, "commit", "-m", message], cwd=cwd)

    def push(self, cwd: Optional[str] = None) -> CommandResult:
        """Push to remote."""
        return self.runner.run([self.binary, "push"], cwd=cwd)

    def pull(self, cwd: Optional[str] = None) -> CommandResult:
        """Pull from remote."""
        return self.runner.run([self.binary, "pull"], cwd=cwd)


class GhAdapter:
    """GitHub CLI adapter."""

    def __init__(self, runner: ProcessRunner) -> None:
        self.runner = runner
        self.binary = get_selected_tool_path("gh", "vcs")

    def version(self) -> ToolProbe:
        """Get GitHub CLI version information."""
        try:
            res = self.runner.run([self.binary, "--version"])
            # Extract version from output like "gh version 2.32.1 (2023-07-18)"
            version = None
            if res.stdout:
                lines = res.stdout.strip().split("\n")
                if lines:
                    parts = lines[0].split()
                    if len(parts) >= 3:
                        version = parts[2]

            return ToolProbe(
                name="gh",
                path=self.binary,
                version=version,
                ok=res.code == 0,
                details=res.stderr if res.code != 0 else None,
            )
        except Exception as e:
            return ToolProbe(
                name="gh",
                path=None,
                version=None,
                ok=False,
                details=str(e),
            )

    def clone(self, url: str, target_dir: str) -> CommandResult:
        """Clone a repository using GitHub CLI."""
        return self.runner.run([self.binary, "repo", "clone", url, target_dir])

    def status(self, cwd: Optional[str] = None) -> CommandResult:
        """Get repository status (delegates to git)."""
        git_adapter = GitAdapter(self.runner)
        return git_adapter.status(cwd=cwd)

    def checkout(self, branch: str, cwd: Optional[str] = None) -> CommandResult:
        """Checkout a branch (delegates to git)."""
        git_adapter = GitAdapter(self.runner)
        return git_adapter.checkout(branch, cwd=cwd)

    def fetch(self, cwd: Optional[str] = None) -> CommandResult:
        """Fetch from remote (delegates to git)."""
        git_adapter = GitAdapter(self.runner)
        return git_adapter.fetch(cwd=cwd)

    def pr_create(
        self, title: str, body: str = "", cwd: Optional[str] = None
    ) -> CommandResult:
        """Create a pull request."""
        return self.runner.run(
            [self.binary, "pr", "create", "--title", title, "--body", body], cwd=cwd
        )

    def pr_list(self, cwd: Optional[str] = None) -> CommandResult:
        """List pull requests."""
        return self.runner.run([self.binary, "pr", "list"], cwd=cwd)

    def auth_status(self) -> CommandResult:
        """Check authentication status."""
        return self.runner.run([self.binary, "auth", "status"])


def create_vcs_adapter(runner: ProcessRunner, vcs_type: str = "git") -> VCS:
    """Factory function to create VCS adapter."""
    if vcs_type == "gh":
        return GhAdapter(runner)
    else:
        return GitAdapter(runner)
