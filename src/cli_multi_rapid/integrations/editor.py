"""Editor integrations (VS Code)."""

import logging
from dataclasses import dataclass
from typing import Any, Dict, Optional

from .process import ProcessResult, ProcessRunner

logger = logging.getLogger(__name__)


@dataclass
class EditorVersion:
    """Version information for editor tools."""

    version: str
    tool: str

    def __str__(self) -> str:
        return f"{self.tool} {self.version}"


class EditorAdapter:
    """Adapter for editor operations (VS Code)."""

    def __init__(self, runner: ProcessRunner, config: Dict[str, Any]):
        """Initialize editor adapter.

        Args:
            runner: ProcessRunner instance
            config: Editor configuration with tool paths
        """
        self.runner = runner
        self.config = config
        self.code_path = self._get_tool_path("code")

    def _get_tool_path(self, tool_name: str) -> str:
        """Get tool path from configuration."""
        tool_config = self.config.get(tool_name)
        if tool_config and hasattr(tool_config, "path"):
            return tool_config.path
        return tool_name  # Fallback to tool name

    def version(self) -> EditorVersion:
        """Get VS Code version information."""
        result = self.runner.run(f'"{self.code_path}" --version')
        if result.ok:
            lines = result.stdout.strip().split("\n")
            version_num = lines[0] if lines else "unknown"
            return EditorVersion(version=version_num, tool="code")
        else:
            return EditorVersion(version="unknown", tool="code")

    def open_file(self, file_path: str) -> ProcessResult:
        """Open a file in VS Code.

        Args:
            file_path: Path to the file to open

        Returns:
            ProcessResult from code command
        """
        return self.runner.run(f'"{self.code_path}" "{file_path}"')

    def open_folder(self, folder_path: str) -> ProcessResult:
        """Open a folder in VS Code.

        Args:
            folder_path: Path to the folder to open

        Returns:
            ProcessResult from code command
        """
        return self.runner.run(f'"{self.code_path}" "{folder_path}"')

    def install_extension(self, extension_id: str) -> ProcessResult:
        """Install a VS Code extension.

        Args:
            extension_id: Extension identifier (e.g., 'ms-python.python')

        Returns:
            ProcessResult from code --install-extension
        """
        return self.runner.run(f'"{self.code_path}" --install-extension {extension_id}')

    def uninstall_extension(self, extension_id: str) -> ProcessResult:
        """Uninstall a VS Code extension.

        Args:
            extension_id: Extension identifier

        Returns:
            ProcessResult from code --uninstall-extension
        """
        return self.runner.run(
            f'"{self.code_path}" --uninstall-extension {extension_id}'
        )

    def list_extensions(self) -> ProcessResult:
        """List installed VS Code extensions.

        Returns:
            ProcessResult with extension list
        """
        return self.runner.run(f'"{self.code_path}" --list-extensions')

    def open_with_wait(self, file_path: str) -> ProcessResult:
        """Open a file and wait for it to be closed.

        Args:
            file_path: Path to the file to open

        Returns:
            ProcessResult from code --wait
        """
        return self.runner.run(f'"{self.code_path}" --wait "{file_path}"')

    def diff(self, file1: str, file2: str) -> ProcessResult:
        """Open diff view between two files.

        Args:
            file1: First file path
            file2: Second file path

        Returns:
            ProcessResult from code --diff
        """
        return self.runner.run(f'"{self.code_path}" --diff "{file1}" "{file2}"')

    def new_window(self, folder_path: Optional[str] = None) -> ProcessResult:
        """Open a new VS Code window.

        Args:
            folder_path: Optional folder to open in new window

        Returns:
            ProcessResult from code --new-window
        """
        cmd = f'"{self.code_path}" --new-window'
        if folder_path:
            cmd += f' "{folder_path}"'
        return self.runner.run(cmd)

    def goto_line(
        self, file_path: str, line: int, column: Optional[int] = None
    ) -> ProcessResult:
        """Open file and go to specific line/column.

        Args:
            file_path: Path to the file
            line: Line number
            column: Column number (optional)

        Returns:
            ProcessResult from code --goto
        """
        location = f"{line}"
        if column:
            location += f":{column}"
        return self.runner.run(f'"{self.code_path}" --goto "{file_path}:{location}"')

    def enable_extension(self, extension_id: str) -> ProcessResult:
        """Enable a VS Code extension.

        Args:
            extension_id: Extension identifier

        Returns:
            ProcessResult from code command
        """
        return self.runner.run(f'"{self.code_path}" --enable-extension {extension_id}')

    def disable_extension(self, extension_id: str) -> ProcessResult:
        """Disable a VS Code extension.

        Args:
            extension_id: Extension identifier

        Returns:
            ProcessResult from code command
        """
        return self.runner.run(f'"{self.code_path}" --disable-extension {extension_id}')

    def show_extensions(self, show_versions: bool = False) -> ProcessResult:
        """Show detailed extension information.

        Args:
            show_versions: Include version information

        Returns:
            ProcessResult with extension details
        """
        cmd = f'"{self.code_path}" --list-extensions'
        if show_versions:
            cmd += " --show-versions"
        return self.runner.run(cmd)

    def merge(self, base: str, theirs: str, yours: str, output: str) -> ProcessResult:
        """Open merge editor for resolving conflicts.

        Args:
            base: Base file path
            theirs: Their changes file path
            yours: Your changes file path
            output: Output file path

        Returns:
            ProcessResult from code --merge
        """
        return self.runner.run(
            f'"{self.code_path}" --merge "{base}" "{theirs}" "{yours}" "{output}"'
        )

    def user_data_dir(self, data_dir: str) -> ProcessResult:
        """Start VS Code with custom user data directory.

        Args:
            data_dir: User data directory path

        Returns:
            ProcessResult from code --user-data-dir
        """
        return self.runner.run(f'"{self.code_path}" --user-data-dir "{data_dir}"')

    def verbose(self) -> ProcessResult:
        """Start VS Code with verbose logging.

        Returns:
            ProcessResult from code --verbose
        """
        return self.runner.run(f'"{self.code_path}" --verbose')

    def log_level(self, level: str) -> ProcessResult:
        """Start VS Code with specific log level.

        Args:
            level: Log level (critical, error, warn, info, debug, trace, silent)

        Returns:
            ProcessResult from code --log
        """
        return self.runner.run(f'"{self.code_path}" --log {level}')


def create_editor_adapter(
    runner: ProcessRunner, config: Dict[str, Any]
) -> EditorAdapter:
    """Create an editor adapter instance.

    Args:
        runner: ProcessRunner instance
        config: Editor configuration

    Returns:
        EditorAdapter instance
    """
    return EditorAdapter(runner, config)
