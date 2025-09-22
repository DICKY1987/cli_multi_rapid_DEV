"""AI CLI adapters."""

from __future__ import annotations

from .process import CommandResult, ProcessRunner
from .registry import get_selected_tool_path
from .tools_base import AICLI, ToolProbe


class ClaudeAdapter:
    """Claude CLI adapter."""

    def __init__(self, runner: ProcessRunner) -> None:
        self.runner = runner
        self.binary = get_selected_tool_path("claude", "ai_cli")

    def version(self) -> ToolProbe:
        """Get Claude CLI version information."""
        try:
            res = self.runner.run([self.binary, "--version"])
            # Extract version from output
            version = None
            if res.stdout:
                # Handle various version output formats
                output = res.stdout.strip()
                if "version" in output.lower():
                    parts = output.split()
                    for i, part in enumerate(parts):
                        if "version" in part.lower() and i + 1 < len(parts):
                            version = parts[i + 1]
                            break
                else:
                    version = output

            return ToolProbe(
                name="claude",
                path=self.binary,
                version=version,
                ok=res.code == 0,
                details=res.stderr if res.code != 0 else None,
            )
        except Exception as e:
            return ToolProbe(
                name="claude",
                path=None,
                version=None,
                ok=False,
                details=str(e),
            )

    def run_command(self, args: list[str], cwd: str | None = None) -> CommandResult:
        """Run a Claude CLI command."""
        cmd_args = [self.binary] + args
        return self.runner.run(cmd_args, cwd=cwd)

    def chat(
        self, message: str, model: str | None = None, cwd: str | None = None
    ) -> CommandResult:
        """Start a chat session with Claude."""
        args = ["chat"]
        if model:
            args.extend(["--model", model])
        args.append(message)
        return self.run_command(args, cwd=cwd)

    def complete(
        self,
        prompt: str,
        model: str | None = None,
        max_tokens: int | None = None,
        cwd: str | None = None,
    ) -> CommandResult:
        """Get a completion from Claude."""
        args = ["complete"]
        if model:
            args.extend(["--model", model])
        if max_tokens:
            args.extend(["--max-tokens", str(max_tokens)])
        args.append(prompt)
        return self.run_command(args, cwd=cwd)

    def analyze_file(
        self, file_path: str, instruction: str, cwd: str | None = None
    ) -> CommandResult:
        """Analyze a file with Claude."""
        args = ["analyze", file_path, instruction]
        return self.run_command(args, cwd=cwd)


class OpenAIAdapter:
    """OpenAI CLI adapter."""

    def __init__(self, runner: ProcessRunner) -> None:
        self.runner = runner
        self.binary = get_selected_tool_path("openai", "ai_cli")
        # Check if we need to use npx
        if self.binary == "openai":
            # Try to use npx if direct openai binary is not available
            self.use_npx = True
            self.npx_binary = get_selected_tool_path("npx", "js_runtime")
        else:
            self.use_npx = False

    def version(self) -> ToolProbe:
        """Get OpenAI CLI version information."""
        try:
            if self.use_npx:
                res = self.runner.run([self.npx_binary, "openai", "--version"])
            else:
                res = self.runner.run([self.binary, "--version"])

            version = None
            if res.stdout:
                output = res.stdout.strip()
                # Extract version number
                import re

                match = re.search(r"(\d+\.\d+\.\d+)", output)
                if match:
                    version = match.group(1)

            return ToolProbe(
                name="openai",
                path=self.binary,
                version=version,
                ok=res.code == 0,
                details=res.stderr if res.code != 0 else None,
            )
        except Exception as e:
            return ToolProbe(
                name="openai",
                path=None,
                version=None,
                ok=False,
                details=str(e),
            )

    def run_command(self, args: list[str], cwd: str | None = None) -> CommandResult:
        """Run an OpenAI CLI command."""
        if self.use_npx:
            cmd_args = [self.npx_binary, "openai"] + args
        else:
            cmd_args = [self.binary] + args
        return self.runner.run(cmd_args, cwd=cwd)

    def chat_completion(
        self,
        message: str,
        model: str = "gpt-3.5-turbo",
        max_tokens: int | None = None,
        cwd: str | None = None,
    ) -> CommandResult:
        """Create a chat completion."""
        args = ["api", "chat_completions.create", "-m", model, "--message", message]
        if max_tokens:
            args.extend(["--max-tokens", str(max_tokens)])
        return self.run_command(args, cwd=cwd)

    def completion(
        self,
        prompt: str,
        model: str = "text-davinci-003",
        max_tokens: int | None = None,
        cwd: str | None = None,
    ) -> CommandResult:
        """Create a text completion."""
        args = ["api", "completions.create", "-m", model, "-p", prompt]
        if max_tokens:
            args.extend(["--max-tokens", str(max_tokens)])
        return self.run_command(args, cwd=cwd)

    def list_models(self, cwd: str | None = None) -> CommandResult:
        """List available models."""
        return self.run_command(["api", "models.list"], cwd=cwd)

    def embedding(
        self,
        text: str,
        model: str = "text-embedding-ada-002",
        cwd: str | None = None,
    ) -> CommandResult:
        """Create embeddings."""
        args = ["api", "embeddings.create", "-m", model, "-i", text]
        return self.run_command(args, cwd=cwd)


def create_ai_cli_adapter(runner: ProcessRunner, ai_type: str = "claude") -> AICLI:
    """Factory function to create AI CLI adapter."""
    if ai_type == "claude":
        return ClaudeAdapter(runner)
    elif ai_type == "openai":
        return OpenAIAdapter(runner)
    else:
        raise ValueError(f"Unsupported AI CLI type: {ai_type}")
