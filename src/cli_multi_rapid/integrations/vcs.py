"""Version Control System integrations."""

import logging
from dataclasses import dataclass
from typing import Any, Dict, Optional

from .process import ProcessResult, ProcessRunner

logger = logging.getLogger(__name__)


@dataclass
class VCSVersion:
    """Version information for VCS tools."""

    version: str
    tool: str

    def __str__(self) -> str:
        return f"{self.tool} {self.version}"


class VCSAdapter:
    """Adapter for Version Control System operations."""

    def __init__(self, runner: ProcessRunner, config: Dict[str, Any]):
        """Initialize VCS adapter.

        Args:
            runner: ProcessRunner instance
            config: VCS configuration with tool paths
        """
        self.runner = runner
        self.config = config
        self.git_path = self._get_tool_path("git")
        self.git_lfs_path = self._get_tool_path("git_lfs")

    def _get_tool_path(self, tool_name: str) -> str:
        """Get tool path from configuration."""
        tool_config = self.config.get(tool_name)
        if tool_config and hasattr(tool_config, "path"):
            return tool_config.path
        return tool_name  # Fallback to tool name

    def version(self) -> VCSVersion:
        """Get git version information."""
        result = self.runner.run(f'"{self.git_path}" --version')
        if result.ok:
            version_str = result.stdout.strip()
            # Extract version number from "git version X.Y.Z"
            if "git version" in version_str:
                version_num = version_str.split("git version")[1].strip()
            else:
                version_num = version_str
            return VCSVersion(version=version_num, tool="git")
        else:
            return VCSVersion(version="unknown", tool="git")

    def status(self, cwd: Optional[str] = None) -> ProcessResult:
        """Get git status.

        Args:
            cwd: Working directory (optional)

        Returns:
            ProcessResult with git status output
        """
        return self.runner.run(f'"{self.git_path}" status --porcelain', cwd=cwd)

    def clone(self, url: str, target_dir: str) -> ProcessResult:
        """Clone a git repository.

        Args:
            url: Repository URL to clone
            target_dir: Target directory for clone

        Returns:
            ProcessResult from git clone operation
        """
        return self.runner.run(f'"{self.git_path}" clone "{url}" "{target_dir}"')

    def checkout(self, branch: str, cwd: Optional[str] = None) -> ProcessResult:
        """Checkout a git branch.

        Args:
            branch: Branch name to checkout
            cwd: Working directory (optional)

        Returns:
            ProcessResult from git checkout operation
        """
        return self.runner.run(f'"{self.git_path}" checkout "{branch}"', cwd=cwd)

    def fetch(self, cwd: Optional[str] = None) -> ProcessResult:
        """Fetch from remote repository.

        Args:
            cwd: Working directory (optional)

        Returns:
            ProcessResult from git fetch operation
        """
        return self.runner.run(f'"{self.git_path}" fetch', cwd=cwd)

    def pull(self, cwd: Optional[str] = None) -> ProcessResult:
        """Pull from remote repository.

        Args:
            cwd: Working directory (optional)

        Returns:
            ProcessResult from git pull operation
        """
        return self.runner.run(f'"{self.git_path}" pull', cwd=cwd)

    def add(self, files: str = ".", cwd: Optional[str] = None) -> ProcessResult:
        """Add files to git staging area.

        Args:
            files: Files to add (default: all files)
            cwd: Working directory (optional)

        Returns:
            ProcessResult from git add operation
        """
        return self.runner.run(f'"{self.git_path}" add {files}', cwd=cwd)

    def commit(self, message: str, cwd: Optional[str] = None) -> ProcessResult:
        """Create a git commit.

        Args:
            message: Commit message
            cwd: Working directory (optional)

        Returns:
            ProcessResult from git commit operation
        """
        return self.runner.run(f'"{self.git_path}" commit -m "{message}"', cwd=cwd)

    def push(
        self,
        remote: str = "origin",
        branch: Optional[str] = None,
        cwd: Optional[str] = None,
    ) -> ProcessResult:
        """Push commits to remote repository.

        Args:
            remote: Remote name (default: origin)
            branch: Branch to push (optional, uses current branch if not specified)
            cwd: Working directory (optional)

        Returns:
            ProcessResult from git push operation
        """
        cmd = f'"{self.git_path}" push {remote}'
        if branch:
            cmd += f" {branch}"
        return self.runner.run(cmd, cwd=cwd)

    def branch_list(self, cwd: Optional[str] = None) -> ProcessResult:
        """List git branches.

        Args:
            cwd: Working directory (optional)

        Returns:
            ProcessResult with branch list
        """
        return self.runner.run(f'"{self.git_path}" branch', cwd=cwd)

    def diff(self, cwd: Optional[str] = None) -> ProcessResult:
        """Show git diff.

        Args:
            cwd: Working directory (optional)

        Returns:
            ProcessResult with diff output
        """
        return self.runner.run(f'"{self.git_path}" diff', cwd=cwd)

    def log(self, limit: int = 10, cwd: Optional[str] = None) -> ProcessResult:
        """Show git log.

        Args:
            limit: Number of commits to show
            cwd: Working directory (optional)

        Returns:
            ProcessResult with log output
        """
        return self.runner.run(f'"{self.git_path}" log --oneline -n {limit}', cwd=cwd)

    def lfs_version(self) -> VCSVersion:
        """Get git-lfs version information."""
        result = self.runner.run(f'"{self.git_lfs_path}" version')
        if result.ok:
            version_str = result.stdout.strip()
            # Extract version from git-lfs output
            if "git-lfs/" in version_str:
                version_num = version_str.split("git-lfs/")[1].split()[0]
            else:
                version_num = version_str
            return VCSVersion(version=version_num, tool="git-lfs")
        else:
            return VCSVersion(version="unknown", tool="git-lfs")

    def lfs_install(self, cwd: Optional[str] = None) -> ProcessResult:
        """Install git-lfs hooks.

        Args:
            cwd: Working directory (optional)

        Returns:
            ProcessResult from git lfs install
        """
        return self.runner.run(f'"{self.git_lfs_path}" install', cwd=cwd)

    def lfs_track(self, pattern: str, cwd: Optional[str] = None) -> ProcessResult:
        """Track files with git-lfs.

        Args:
            pattern: File pattern to track
            cwd: Working directory (optional)

        Returns:
            ProcessResult from git lfs track
        """
        return self.runner.run(f'"{self.git_lfs_path}" track "{pattern}"', cwd=cwd)


def create_vcs_adapter(runner: ProcessRunner, config: Dict[str, Any]) -> VCSAdapter:
    """Create a VCS adapter instance.

    Args:
        runner: ProcessRunner instance
        config: VCS configuration

    Returns:
        VCSAdapter instance
    """
    return VCSAdapter(runner, config)
