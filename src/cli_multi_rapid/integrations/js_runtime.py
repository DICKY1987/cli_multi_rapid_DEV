"""JavaScript runtime integrations (Node.js, npm, pnpm)."""

import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from .process import ProcessResult, ProcessRunner

logger = logging.getLogger(__name__)


@dataclass
class JSRuntimeVersion:
    """Version information for JavaScript runtime tools."""

    version: str
    tool: str

    def __str__(self) -> str:
        return f"{self.tool} {self.version}"


class JSRuntimeAdapter:
    """Adapter for JavaScript runtime operations."""

    def __init__(self, runner: ProcessRunner, config: Dict[str, Any]):
        """Initialize JS runtime adapter.

        Args:
            runner: ProcessRunner instance
            config: JS runtime configuration with tool paths
        """
        self.runner = runner
        self.config = config
        self.node_path = self._get_tool_path("node")
        self.pnpm_path = self._get_tool_path("pnpm")

    def _get_tool_path(self, tool_name: str) -> str:
        """Get tool path from configuration."""
        tool_config = self.config.get(tool_name)
        if tool_config and hasattr(tool_config, "path"):
            return tool_config.path
        return tool_name  # Fallback to tool name

    def version(self) -> JSRuntimeVersion:
        """Get Node.js version information."""
        result = self.runner.run(f'"{self.node_path}" --version')
        if result.ok:
            version_str = result.stdout.strip()
            # Node version typically starts with 'v'
            version_num = version_str.lstrip("v")
            return JSRuntimeVersion(version=version_num, tool="node")
        else:
            return JSRuntimeVersion(version="unknown", tool="node")

    def npm_version(self) -> JSRuntimeVersion:
        """Get npm version information."""
        result = self.runner.run("npm --version")
        if result.ok:
            version_str = result.stdout.strip()
            return JSRuntimeVersion(version=version_str, tool="npm")
        else:
            return JSRuntimeVersion(version="unknown", tool="npm")

    def pnpm_version(self) -> JSRuntimeVersion:
        """Get pnpm version information."""
        result = self.runner.run(f'"{self.pnpm_path}" --version')
        if result.ok:
            version_str = result.stdout.strip()
            return JSRuntimeVersion(version=version_str, tool="pnpm")
        else:
            return JSRuntimeVersion(version="unknown", tool="pnpm")

    def npm_install(
        self, cwd: Optional[str] = None, package: Optional[str] = None
    ) -> ProcessResult:
        """Run npm install.

        Args:
            cwd: Working directory (optional)
            package: Specific package to install (optional)

        Returns:
            ProcessResult from npm install
        """
        cmd = "npm install"
        if package:
            cmd += f" {package}"
        return self.runner.run(cmd, cwd=cwd)

    def npm_run(
        self, script: str, cwd: Optional[str] = None, args: Optional[List[str]] = None
    ) -> ProcessResult:
        """Run npm script.

        Args:
            script: Script name to run
            cwd: Working directory (optional)
            args: Additional arguments (optional)

        Returns:
            ProcessResult from npm run
        """
        cmd = f"npm run {script}"
        if args:
            cmd += " -- " + " ".join(args)
        return self.runner.run(cmd, cwd=cwd)

    def npx_run(
        self, package: str, args: Optional[List[str]] = None, cwd: Optional[str] = None
    ) -> ProcessResult:
        """Run package with npx.

        Args:
            package: Package to run
            args: Arguments for the package
            cwd: Working directory (optional)

        Returns:
            ProcessResult from npx
        """
        cmd = f"npx {package}"
        if args:
            cmd += " " + " ".join(args)
        return self.runner.run(cmd, cwd=cwd)

    def pnpm_install(
        self, cwd: Optional[str] = None, package: Optional[str] = None
    ) -> ProcessResult:
        """Run pnpm install.

        Args:
            cwd: Working directory (optional)
            package: Specific package to install (optional)

        Returns:
            ProcessResult from pnpm install
        """
        cmd = f'"{self.pnpm_path}" install'
        if package:
            cmd += f" {package}"
        return self.runner.run(cmd, cwd=cwd)

    def pnpm_run(
        self, script: str, cwd: Optional[str] = None, args: Optional[List[str]] = None
    ) -> ProcessResult:
        """Run pnpm script.

        Args:
            script: Script name to run
            cwd: Working directory (optional)
            args: Additional arguments (optional)

        Returns:
            ProcessResult from pnpm run
        """
        cmd = f'"{self.pnpm_path}" run {script}'
        if args:
            cmd += " -- " + " ".join(args)
        return self.runner.run(cmd, cwd=cwd)

    def pnpm_exec(
        self, package: str, args: Optional[List[str]] = None, cwd: Optional[str] = None
    ) -> ProcessResult:
        """Execute package with pnpm exec.

        Args:
            package: Package to execute
            args: Arguments for the package
            cwd: Working directory (optional)

        Returns:
            ProcessResult from pnpm exec
        """
        cmd = f'"{self.pnpm_path}" exec {package}'
        if args:
            cmd += " " + " ".join(args)
        return self.runner.run(cmd, cwd=cwd)

    def npm_list(
        self, global_packages: bool = False, cwd: Optional[str] = None
    ) -> ProcessResult:
        """List installed packages.

        Args:
            global_packages: List global packages
            cwd: Working directory (optional)

        Returns:
            ProcessResult with package list
        """
        cmd = "npm list"
        if global_packages:
            cmd += " -g"
        return self.runner.run(cmd, cwd=cwd)

    def npm_outdated(self, cwd: Optional[str] = None) -> ProcessResult:
        """Check for outdated packages.

        Args:
            cwd: Working directory (optional)

        Returns:
            ProcessResult with outdated packages
        """
        return self.runner.run("npm outdated", cwd=cwd)

    def npm_update(
        self, package: Optional[str] = None, cwd: Optional[str] = None
    ) -> ProcessResult:
        """Update packages.

        Args:
            package: Specific package to update (optional)
            cwd: Working directory (optional)

        Returns:
            ProcessResult from npm update
        """
        cmd = "npm update"
        if package:
            cmd += f" {package}"
        return self.runner.run(cmd, cwd=cwd)

    def npm_audit(self, fix: bool = False, cwd: Optional[str] = None) -> ProcessResult:
        """Run npm audit.

        Args:
            fix: Automatically fix vulnerabilities
            cwd: Working directory (optional)

        Returns:
            ProcessResult from npm audit
        """
        cmd = "npm audit"
        if fix:
            cmd += " fix"
        return self.runner.run(cmd, cwd=cwd)

    def node_run(
        self,
        script_file: str,
        args: Optional[List[str]] = None,
        cwd: Optional[str] = None,
    ) -> ProcessResult:
        """Run a Node.js script.

        Args:
            script_file: Path to the script file
            args: Arguments for the script
            cwd: Working directory (optional)

        Returns:
            ProcessResult from node
        """
        cmd = f'"{self.node_path}" "{script_file}"'
        if args:
            cmd += " " + " ".join(args)
        return self.runner.run(cmd, cwd=cwd)

    def node_eval(self, code: str, cwd: Optional[str] = None) -> ProcessResult:
        """Evaluate JavaScript code with Node.js.

        Args:
            code: JavaScript code to evaluate
            cwd: Working directory (optional)

        Returns:
            ProcessResult from node -e
        """
        return self.runner.run(f'"{self.node_path}" -e "{code}"', cwd=cwd)

    def npm_init(self, yes: bool = False, cwd: Optional[str] = None) -> ProcessResult:
        """Initialize a new npm package.

        Args:
            yes: Use default values
            cwd: Working directory (optional)

        Returns:
            ProcessResult from npm init
        """
        cmd = "npm init"
        if yes:
            cmd += " -y"
        return self.runner.run(cmd, cwd=cwd)

    def pnpm_add(
        self, package: str, dev: bool = False, cwd: Optional[str] = None
    ) -> ProcessResult:
        """Add a package with pnpm.

        Args:
            package: Package to add
            dev: Add as development dependency
            cwd: Working directory (optional)

        Returns:
            ProcessResult from pnpm add
        """
        cmd = f'"{self.pnpm_path}" add {package}'
        if dev:
            cmd += " --save-dev"
        return self.runner.run(cmd, cwd=cwd)

    def pnpm_remove(self, package: str, cwd: Optional[str] = None) -> ProcessResult:
        """Remove a package with pnpm.

        Args:
            package: Package to remove
            cwd: Working directory (optional)

        Returns:
            ProcessResult from pnpm remove
        """
        return self.runner.run(f'"{self.pnpm_path}" remove {package}', cwd=cwd)


def create_js_runtime_adapter(
    runner: ProcessRunner, config: Dict[str, Any]
) -> JSRuntimeAdapter:
    """Create a JS runtime adapter instance.

    Args:
        runner: ProcessRunner instance
        config: JS runtime configuration

    Returns:
        JSRuntimeAdapter instance
    """
    return JSRuntimeAdapter(runner, config)
