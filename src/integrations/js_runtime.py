"""JavaScript runtime adapters."""

from __future__ import annotations

from .process import CommandResult, ProcessRunner
from .registry import get_selected_tool_path
from .tools_base import JSRuntime, ToolProbe


class NodeAdapter:
    """Node.js runtime adapter."""

    def __init__(self, runner: ProcessRunner) -> None:
        self.runner = runner
        self.node_binary = get_selected_tool_path("node", "js_runtime")
        self.npx_binary = get_selected_tool_path("npx", "js_runtime")

    def version(self) -> ToolProbe:
        """Get Node.js version information."""
        try:
            res = self.runner.run([self.node_binary, "--version"])
            # Extract version from output like "v18.17.0"
            version = None
            if res.stdout:
                version = res.stdout.strip().lstrip("v")

            return ToolProbe(
                name="node",
                path=self.node_binary,
                version=version,
                ok=res.code == 0,
                details=res.stderr if res.code != 0 else None,
            )
        except Exception as e:
            return ToolProbe(
                name="node",
                path=None,
                version=None,
                ok=False,
                details=str(e),
            )

    def npm_install(self, cwd: str | None = None) -> CommandResult:
        """Run npm install."""
        return self.runner.run(
            [
                self.node_binary,
                "-e",
                "require('child_process').execSync('npm install', {stdio: 'inherit'})",
            ],
            cwd=cwd,
        )

    def npm_run(self, script: str, cwd: str | None = None) -> CommandResult:
        """Run an npm script."""
        return self.runner.run(
            [
                self.node_binary,
                "-e",
                f"require('child_process').execSync('npm run {script}', {{stdio: 'inherit'}})",
            ],
            cwd=cwd,
        )

    def npx_run(
        self, package: str, args: list[str] | None = None, cwd: str | None = None
    ) -> CommandResult:
        """Run a package with npx."""
        cmd_args = [self.npx_binary, package]
        if args:
            cmd_args.extend(args)
        return self.runner.run(cmd_args, cwd=cwd)

    def npm_init(self, cwd: str | None = None, yes: bool = False) -> CommandResult:
        """Initialize a new npm project."""
        cmd = "npm init"
        if yes:
            cmd += " -y"
        return self.runner.run(
            [
                self.node_binary,
                "-e",
                f"require('child_process').execSync('{cmd}', {{stdio: 'inherit'}})",
            ],
            cwd=cwd,
        )

    def npm_install_package(
        self,
        package: str,
        dev: bool = False,
        global_install: bool = False,
        cwd: str | None = None,
    ) -> CommandResult:
        """Install a specific npm package."""
        cmd = f"npm install {package}"
        if dev:
            cmd += " --save-dev"
        if global_install:
            cmd += " -g"
        return self.runner.run(
            [
                self.node_binary,
                "-e",
                f"require('child_process').execSync('{cmd}', {{stdio: 'inherit'}})",
            ],
            cwd=cwd,
        )

    def npm_uninstall_package(
        self, package: str, cwd: str | None = None
    ) -> CommandResult:
        """Uninstall an npm package."""
        cmd = f"npm uninstall {package}"
        return self.runner.run(
            [
                self.node_binary,
                "-e",
                f"require('child_process').execSync('{cmd}', {{stdio: 'inherit'}})",
            ],
            cwd=cwd,
        )

    def npm_list(
        self, global_list: bool = False, cwd: str | None = None
    ) -> CommandResult:
        """List installed npm packages."""
        cmd = "npm list"
        if global_list:
            cmd += " -g"
        return self.runner.run(
            [
                self.node_binary,
                "-e",
                f"require('child_process').execSync('{cmd}', {{stdio: 'inherit'}})",
            ],
            cwd=cwd,
        )

    def npm_audit(self, fix: bool = False, cwd: str | None = None) -> CommandResult:
        """Run npm audit."""
        cmd = "npm audit"
        if fix:
            cmd += " fix"
        return self.runner.run(
            [
                self.node_binary,
                "-e",
                f"require('child_process').execSync('{cmd}', {{stdio: 'inherit'}})",
            ],
            cwd=cwd,
        )

    def npm_test(self, cwd: str | None = None) -> CommandResult:
        """Run npm test."""
        return self.npm_run("test", cwd=cwd)

    def npm_build(self, cwd: str | None = None) -> CommandResult:
        """Run npm build."""
        return self.npm_run("build", cwd=cwd)

    def npm_start(self, cwd: str | None = None) -> CommandResult:
        """Run npm start."""
        return self.npm_run("start", cwd=cwd)

    def execute_js(self, code: str, cwd: str | None = None) -> CommandResult:
        """Execute JavaScript code directly."""
        return self.runner.run([self.node_binary, "-e", code], cwd=cwd)

    def execute_js_file(self, file_path: str, cwd: str | None = None) -> CommandResult:
        """Execute a JavaScript file."""
        return self.runner.run([self.node_binary, file_path], cwd=cwd)

    def check_package_json(self, cwd: str | None = None) -> CommandResult:
        """Check if package.json exists and is valid."""
        code = """
        const fs = require('fs');
        const path = require('path');
        try {
            const pkg = JSON.parse(fs.readFileSync('package.json', 'utf8'));
            console.log('✓ package.json is valid');
            console.log('Name:', pkg.name);
            console.log('Version:', pkg.version);
        } catch (e) {
            console.error('✗ package.json error:', e.message);
            process.exit(1);
        }
        """
        return self.execute_js(code, cwd=cwd)

    def npx_version(self) -> ToolProbe:
        """Get NPX version information."""
        try:
            res = self.runner.run([self.npx_binary, "--version"])
            version = None
            if res.stdout:
                version = res.stdout.strip()

            return ToolProbe(
                name="npx",
                path=self.npx_binary,
                version=version,
                ok=res.code == 0,
                details=res.stderr if res.code != 0 else None,
            )
        except Exception as e:
            return ToolProbe(
                name="npx",
                path=None,
                version=None,
                ok=False,
                details=str(e),
            )


def create_js_runtime_adapter(
    runner: ProcessRunner, runtime_type: str = "node"
) -> JSRuntime:
    """Factory function to create JS runtime adapter."""
    if runtime_type == "node":
        return NodeAdapter(runner)
    else:
        raise ValueError(f"Unsupported JS runtime type: {runtime_type}")
