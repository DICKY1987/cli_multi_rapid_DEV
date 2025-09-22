"""Code editor adapters."""

from __future__ import annotations

from .process import CommandResult, ProcessRunner
from .registry import get_selected_tool_path
from .tools_base import Editor, ToolProbe


class VSCodeAdapter:
    """Visual Studio Code editor adapter."""

    def __init__(self, runner: ProcessRunner) -> None:
        self.runner = runner
        self.binary = get_selected_tool_path("code", "editor")

    def version(self) -> ToolProbe:
        """Get VS Code version information."""
        try:
            res = self.runner.run([self.binary, "--version"])
            # Extract version from first line of output
            version = None
            if res.stdout:
                lines = res.stdout.strip().split("\n")
                if lines:
                    version = lines[0].strip()

            return ToolProbe(
                name="vscode",
                path=self.binary,
                version=version,
                ok=res.code == 0,
                details=res.stderr if res.code != 0 else None,
            )
        except Exception as e:
            return ToolProbe(
                name="vscode",
                path=None,
                version=None,
                ok=False,
                details=str(e),
            )

    def open_file(self, file_path: str) -> CommandResult:
        """Open a file in VS Code."""
        return self.runner.run([self.binary, file_path])

    def open_folder(self, folder_path: str) -> CommandResult:
        """Open a folder in VS Code."""
        return self.runner.run([self.binary, folder_path])

    def install_extension(self, extension_id: str) -> CommandResult:
        """Install a VS Code extension."""
        return self.runner.run([self.binary, "--install-extension", extension_id])

    def list_extensions(self) -> CommandResult:
        """List installed VS Code extensions."""
        return self.runner.run([self.binary, "--list-extensions"])

    def uninstall_extension(self, extension_id: str) -> CommandResult:
        """Uninstall a VS Code extension."""
        return self.runner.run([self.binary, "--uninstall-extension", extension_id])

    def open_with_wait(self, path: str) -> CommandResult:
        """Open file/folder and wait for the window to close."""
        return self.runner.run([self.binary, "--wait", path])

    def diff(self, file1: str, file2: str) -> CommandResult:
        """Compare two files using VS Code diff."""
        return self.runner.run([self.binary, "--diff", file1, file2])

    def goto(self, file_path: str, line: int, column: int = 1) -> CommandResult:
        """Open file at specific line and column."""
        location = f"{file_path}:{line}:{column}"
        return self.runner.run([self.binary, "--goto", location])

    def new_window(self, path: str = "") -> CommandResult:
        """Open a new VS Code window."""
        args = [self.binary, "--new-window"]
        if path:
            args.append(path)
        return self.runner.run(args)

    def install_recommended_extensions(
        self, extensions: list[str]
    ) -> list[CommandResult]:
        """Install a list of recommended extensions."""
        results = []
        for ext in extensions:
            result = self.install_extension(ext)
            results.append(result)
        return results

    def workspace_settings(self, workspace_path: str, settings: dict) -> CommandResult:
        """Configure workspace settings (via opening settings file)."""
        import json
        import os

        vscode_dir = os.path.join(workspace_path, ".vscode")
        settings_file = os.path.join(vscode_dir, "settings.json")

        # Create .vscode directory if it doesn't exist
        os.makedirs(vscode_dir, exist_ok=True)

        # Write settings to file
        with open(settings_file, "w", encoding="utf-8") as f:
            json.dump(settings, f, indent=2)

        # Open the settings file
        return self.open_file(settings_file)

    def format_document(self, file_path: str) -> CommandResult:
        """Format a document (requires opening VS Code)."""
        # This opens the file - formatting would need to be done interactively
        # or via VS Code tasks/commands API
        return self.open_file(file_path)


def create_editor_adapter(runner: ProcessRunner, editor_type: str = "vscode") -> Editor:
    """Factory function to create editor adapter."""
    if editor_type == "vscode":
        return VSCodeAdapter(runner)
    else:
        raise ValueError(f"Unsupported editor type: {editor_type}")
