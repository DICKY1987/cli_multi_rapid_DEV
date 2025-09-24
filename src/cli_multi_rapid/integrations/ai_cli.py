"""AI CLI tool integrations (Claude, Aider, OpenAI)."""

import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from .process import ProcessResult, ProcessRunner

logger = logging.getLogger(__name__)


@dataclass
class AICLIVersion:
    """Version information for AI CLI tools."""

    version: str
    tool: str

    def __str__(self) -> str:
        return f"{self.tool} {self.version}"


class AICLIAdapter:
    """Adapter for AI CLI tool operations."""

    def __init__(self, runner: ProcessRunner, config: Dict[str, Any]):
        """Initialize AI CLI adapter.

        Args:
            runner: ProcessRunner instance
            config: AI CLI configuration with tool paths
        """
        self.runner = runner
        self.config = config
        self.claude_path = self._get_tool_path("claude")
        self.aider_path = self._get_tool_path("aider")
        self.openai_path = self._get_tool_path("openai")

    def _get_tool_path(self, tool_name: str) -> str:
        """Get tool path from configuration."""
        tool_config = self.config.get(tool_name)
        if tool_config and hasattr(tool_config, "path"):
            return tool_config.path
        return tool_name  # Fallback to tool name

    def version(self) -> AICLIVersion:
        """Get AI CLI tool version information (defaults to aider)."""
        return self.aider_version()

    def claude_version(self) -> AICLIVersion:
        """Get Claude CLI version information."""
        result = self.runner.run(f'"{self.claude_path}" --version')
        if result.ok:
            version_str = result.stdout.strip()
            return AICLIVersion(version=version_str, tool="claude")
        else:
            return AICLIVersion(version="unknown", tool="claude")

    def aider_version(self) -> AICLIVersion:
        """Get Aider version information."""
        result = self.runner.run(f'"{self.aider_path}" --version')
        if result.ok:
            version_str = result.stdout.strip()
            return AICLIVersion(version=version_str, tool="aider")
        else:
            return AICLIVersion(version="unknown", tool="aider")

    def openai_version(self) -> AICLIVersion:
        """Get OpenAI CLI version information."""
        result = self.runner.run(f'"{self.openai_path}" --version')
        if result.ok:
            version_str = result.stdout.strip()
            return AICLIVersion(version=version_str, tool="openai")
        else:
            return AICLIVersion(version="unknown", tool="openai")

    def run_command(
        self, args: List[str], cwd: Optional[str] = None, tool: str = "aider"
    ) -> ProcessResult:
        """Run AI CLI command with specified arguments.

        Args:
            args: Command line arguments
            cwd: Working directory (optional)
            tool: AI tool to use (aider, claude, openai)

        Returns:
            ProcessResult from AI CLI command
        """
        tool_path = getattr(self, f"{tool}_path", self.aider_path)
        cmd = f'"{tool_path}" ' + " ".join(args)
        return self.runner.run(cmd, cwd=cwd)

    def aider_edit(
        self,
        files: List[str],
        message: str,
        cwd: Optional[str] = None,
        model: Optional[str] = None,
        auto_commit: bool = False,
        no_commit: bool = False,
    ) -> ProcessResult:
        """Run aider to edit files with AI assistance.

        Args:
            files: List of files to edit
            message: Description of changes to make
            cwd: Working directory (optional)
            model: AI model to use (optional)
            auto_commit: Automatically commit changes
            no_commit: Don't auto-commit changes

        Returns:
            ProcessResult from aider
        """
        cmd_parts = [f'"{self.aider_path}"']

        # Add files
        for file in files:
            cmd_parts.append(f'"{file}"')

        # Add message
        cmd_parts.extend(["--message", f'"{message}"'])

        # Add model if specified
        if model:
            cmd_parts.extend(["--model", model])

        # Add commit options
        if auto_commit:
            cmd_parts.append("--auto-commits")
        elif no_commit:
            cmd_parts.append("--no-auto-commits")

        return self.runner.run(" ".join(cmd_parts), cwd=cwd)

    def aider_chat(
        self,
        files: List[str],
        cwd: Optional[str] = None,
        model: Optional[str] = None,
        read_only: bool = False,
    ) -> ProcessResult:
        """Start interactive aider chat session.

        Args:
            files: List of files to include in context
            cwd: Working directory (optional)
            model: AI model to use (optional)
            read_only: Open files in read-only mode

        Returns:
            ProcessResult from aider chat
        """
        cmd_parts = [f'"{self.aider_path}"']

        # Add files
        for file in files:
            cmd_parts.append(f'"{file}"')

        # Add model if specified
        if model:
            cmd_parts.extend(["--model", model])

        # Add read-only flag if specified
        if read_only:
            cmd_parts.append("--read")

        return self.runner.run(" ".join(cmd_parts), cwd=cwd)

    def claude_chat(self, message: str, cwd: Optional[str] = None) -> ProcessResult:
        """Send message to Claude CLI.

        Args:
            message: Message to send to Claude
            cwd: Working directory (optional)

        Returns:
            ProcessResult from Claude CLI
        """
        return self.runner.run(f'"{self.claude_path}" "{message}"', cwd=cwd)

    def openai_chat(
        self, message: str, model: str = "gpt-3.5-turbo", cwd: Optional[str] = None
    ) -> ProcessResult:
        """Send message to OpenAI CLI.

        Args:
            message: Message to send
            model: OpenAI model to use
            cwd: Working directory (optional)

        Returns:
            ProcessResult from OpenAI CLI
        """
        cmd = f'"{self.openai_path}" api chat.completions.create -m {model} -g user "{message}"'
        return self.runner.run(cmd, cwd=cwd)

    def aider_add_file(
        self, file_path: str, cwd: Optional[str] = None
    ) -> ProcessResult:
        """Add file to aider session.

        Args:
            file_path: Path to file to add
            cwd: Working directory (optional)

        Returns:
            ProcessResult from aider
        """
        return self.runner.run(f'"{self.aider_path}" --add "{file_path}"', cwd=cwd)

    def aider_remove_file(
        self, file_path: str, cwd: Optional[str] = None
    ) -> ProcessResult:
        """Remove file from aider session.

        Args:
            file_path: Path to file to remove
            cwd: Working directory (optional)

        Returns:
            ProcessResult from aider
        """
        return self.runner.run(f'"{self.aider_path}" --drop "{file_path}"', cwd=cwd)

    def aider_list_models(self) -> ProcessResult:
        """List available aider models.

        Returns:
            ProcessResult with model list
        """
        return self.runner.run(f'"{self.aider_path}" --models')

    def aider_help(self) -> ProcessResult:
        """Get aider help information.

        Returns:
            ProcessResult with help text
        """
        return self.runner.run(f'"{self.aider_path}" --help')

    def openai_models_list(self) -> ProcessResult:
        """List available OpenAI models.

        Returns:
            ProcessResult with model list
        """
        return self.runner.run(f'"{self.openai_path}" api models.list')

    def openai_fine_tune(
        self,
        training_file: str,
        model: str = "gpt-3.5-turbo",
        suffix: Optional[str] = None,
    ) -> ProcessResult:
        """Create OpenAI fine-tuning job.

        Args:
            training_file: Path to training data file
            model: Base model to fine-tune
            suffix: Custom suffix for the fine-tuned model

        Returns:
            ProcessResult from OpenAI fine-tuning
        """
        cmd_parts = [
            f'"{self.openai_path}"',
            "api",
            "fine_tuning.jobs.create",
            "-m",
            model,
            "-t",
            f'"{training_file}"',
        ]

        if suffix:
            cmd_parts.extend(["-s", suffix])

        return self.runner.run(" ".join(cmd_parts))

    def generic_ai_command(
        self,
        tool: str,
        command: str,
        args: Optional[List[str]] = None,
        cwd: Optional[str] = None,
    ) -> ProcessResult:
        """Run generic AI CLI command.

        Args:
            tool: AI tool name (claude, aider, openai)
            command: Command to run
            args: Additional arguments
            cwd: Working directory (optional)

        Returns:
            ProcessResult from AI CLI command
        """
        tool_path = getattr(self, f"{tool}_path", tool)
        cmd_parts = [f'"{tool_path}"', command]

        if args:
            cmd_parts.extend(args)

        return self.runner.run(" ".join(cmd_parts), cwd=cwd)


def create_ai_cli_adapter(
    runner: ProcessRunner, config: Dict[str, Any]
) -> AICLIAdapter:
    """Create an AI CLI adapter instance.

    Args:
        runner: ProcessRunner instance
        config: AI CLI configuration

    Returns:
        AICLIAdapter instance
    """
    return AICLIAdapter(runner, config)
