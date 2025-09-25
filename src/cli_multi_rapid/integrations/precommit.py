"""Pre-commit hook integrations."""

import logging
from dataclasses import dataclass
from typing import List, Optional

from .process import ProcessResult, ProcessRunner

logger = logging.getLogger(__name__)


@dataclass
class PrecommitVersion:
    """Version information for pre-commit tools."""

    version: str
    tool: str

    def __str__(self) -> str:
        return f"{self.tool} {self.version}"


class PrecommitAdapter:
    """Adapter for pre-commit hook operations."""

    def __init__(self, runner: ProcessRunner):
        """Initialize pre-commit adapter.

        Args:
            runner: ProcessRunner instance
        """
        self.runner = runner

    def version(self) -> PrecommitVersion:
        """Get pre-commit version information."""
        result = self.runner.run("pre-commit --version")
        if result.ok:
            version_str = result.stdout.strip()
            # Extract version from "pre-commit X.Y.Z"
            if "pre-commit" in version_str:
                version_num = version_str.split()[-1]
            else:
                version_num = version_str
            return PrecommitVersion(version=version_num, tool="pre-commit")
        else:
            return PrecommitVersion(version="unknown", tool="pre-commit")

    def install(
        self, install_hooks: bool = True, cwd: Optional[str] = None
    ) -> ProcessResult:
        """Install pre-commit hooks.

        Args:
            install_hooks: Whether to install the hooks
            cwd: Working directory (optional)

        Returns:
            ProcessResult from pre-commit install
        """
        cmd = "pre-commit install"
        if not install_hooks:
            cmd += " --install-hooks"
        return self.runner.run(cmd, cwd=cwd)

    def uninstall(self, cwd: Optional[str] = None) -> ProcessResult:
        """Uninstall pre-commit hooks.

        Args:
            cwd: Working directory (optional)

        Returns:
            ProcessResult from pre-commit uninstall
        """
        return self.runner.run("pre-commit uninstall", cwd=cwd)

    def run_all(
        self, all_files: bool = False, cwd: Optional[str] = None
    ) -> ProcessResult:
        """Run all pre-commit hooks.

        Args:
            all_files: Run on all files instead of just staged files
            cwd: Working directory (optional)

        Returns:
            ProcessResult from pre-commit run
        """
        cmd = "pre-commit run"
        if all_files:
            cmd += " --all-files"
        return self.runner.run(cmd, cwd=cwd)

    def run_hook(
        self,
        hook_id: str,
        files: Optional[List[str]] = None,
        all_files: bool = False,
        cwd: Optional[str] = None,
    ) -> ProcessResult:
        """Run specific pre-commit hook.

        Args:
            hook_id: ID of the hook to run
            files: Specific files to run on
            all_files: Run on all files
            cwd: Working directory (optional)

        Returns:
            ProcessResult from pre-commit run
        """
        cmd_parts = ["pre-commit", "run", hook_id]

        if all_files:
            cmd_parts.append("--all-files")
        elif files:
            cmd_parts.append("--files")
            cmd_parts.extend(files)

        return self.runner.run(" ".join(cmd_parts), cwd=cwd)

    def autoupdate(self, cwd: Optional[str] = None) -> ProcessResult:
        """Auto-update pre-commit hook versions.

        Args:
            cwd: Working directory (optional)

        Returns:
            ProcessResult from pre-commit autoupdate
        """
        return self.runner.run("pre-commit autoupdate", cwd=cwd)

    def clean(self, cwd: Optional[str] = None) -> ProcessResult:
        """Clean pre-commit cache.

        Args:
            cwd: Working directory (optional)

        Returns:
            ProcessResult from pre-commit clean
        """
        return self.runner.run("pre-commit clean", cwd=cwd)

    def gc(self, cwd: Optional[str] = None) -> ProcessResult:
        """Garbage collect pre-commit cache.

        Args:
            cwd: Working directory (optional)

        Returns:
            ProcessResult from pre-commit gc
        """
        return self.runner.run("pre-commit gc", cwd=cwd)

    def sample_config(self, cwd: Optional[str] = None) -> ProcessResult:
        """Generate sample pre-commit config.

        Args:
            cwd: Working directory (optional)

        Returns:
            ProcessResult with sample config
        """
        return self.runner.run("pre-commit sample-config", cwd=cwd)

    def validate_config(
        self, config_file: Optional[str] = None, cwd: Optional[str] = None
    ) -> ProcessResult:
        """Validate pre-commit configuration.

        Args:
            config_file: Path to config file (optional)
            cwd: Working directory (optional)

        Returns:
            ProcessResult from pre-commit validate-config
        """
        cmd = "pre-commit validate-config"
        if config_file:
            cmd += f" {config_file}"
        return self.runner.run(cmd, cwd=cwd)

    def validate_manifest(
        self, manifest_file: str, cwd: Optional[str] = None
    ) -> ProcessResult:
        """Validate pre-commit manifest.

        Args:
            manifest_file: Path to manifest file
            cwd: Working directory (optional)

        Returns:
            ProcessResult from pre-commit validate-manifest
        """
        return self.runner.run(f"pre-commit validate-manifest {manifest_file}", cwd=cwd)

    def migrate_config(self, cwd: Optional[str] = None) -> ProcessResult:
        """Migrate pre-commit configuration.

        Args:
            cwd: Working directory (optional)

        Returns:
            ProcessResult from pre-commit migrate-config
        """
        return self.runner.run("pre-commit migrate-config", cwd=cwd)

    def try_repo(
        self,
        repo_url: str,
        hooks: Optional[List[str]] = None,
        ref: Optional[str] = None,
        cwd: Optional[str] = None,
    ) -> ProcessResult:
        """Try a pre-commit repository.

        Args:
            repo_url: Repository URL
            hooks: List of hooks to try
            ref: Git reference to use
            cwd: Working directory (optional)

        Returns:
            ProcessResult from pre-commit try-repo
        """
        cmd_parts = ["pre-commit", "try-repo", repo_url]

        if ref:
            cmd_parts.extend(["--ref", ref])

        if hooks:
            cmd_parts.append("--")
            cmd_parts.extend(hooks)

        return self.runner.run(" ".join(cmd_parts), cwd=cwd)

    def install_hooks(self, cwd: Optional[str] = None) -> ProcessResult:
        """Install pre-commit hooks without git hooks.

        Args:
            cwd: Working directory (optional)

        Returns:
            ProcessResult from pre-commit install-hooks
        """
        return self.runner.run("pre-commit install-hooks", cwd=cwd)

    def init_templatedir(
        self, template_dir: str, hook_type: str = "pre-commit"
    ) -> ProcessResult:
        """Initialize template directory.

        Args:
            template_dir: Template directory path
            hook_type: Type of hook to initialize

        Returns:
            ProcessResult from pre-commit init-templatedir
        """
        return self.runner.run(
            f"pre-commit init-templatedir {template_dir} --hook-type {hook_type}"
        )

    def check_for_updates(self, cwd: Optional[str] = None) -> ProcessResult:
        """Check for pre-commit updates without updating.

        Args:
            cwd: Working directory (optional)

        Returns:
            ProcessResult showing available updates
        """
        return self.runner.run("pre-commit autoupdate --dry-run", cwd=cwd)

    def list_hooks(self, cwd: Optional[str] = None) -> ProcessResult:
        """List configured pre-commit hooks.

        Args:
            cwd: Working directory (optional)

        Returns:
            ProcessResult with hook list
        """
        # This uses a workaround since pre-commit doesn't have a direct list command
        return self.runner.run("pre-commit run --all-files --dry-run", cwd=cwd)

    def run_specific_files(
        self, files: List[str], hook_id: Optional[str] = None, cwd: Optional[str] = None
    ) -> ProcessResult:
        """Run pre-commit on specific files.

        Args:
            files: List of files to check
            hook_id: Specific hook to run (optional)
            cwd: Working directory (optional)

        Returns:
            ProcessResult from pre-commit run
        """
        cmd_parts = ["pre-commit", "run"]

        if hook_id:
            cmd_parts.append(hook_id)

        cmd_parts.append("--files")
        cmd_parts.extend(files)

        return self.runner.run(" ".join(cmd_parts), cwd=cwd)


def create_precommit_adapter(runner: ProcessRunner) -> PrecommitAdapter:
    """Create a pre-commit adapter instance.

    Args:
        runner: ProcessRunner instance

    Returns:
        PrecommitAdapter instance
    """
    return PrecommitAdapter(runner)
