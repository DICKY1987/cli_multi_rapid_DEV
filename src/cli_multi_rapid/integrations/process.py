"""Process execution utilities for tool integrations."""

import logging
import subprocess
from dataclasses import dataclass
from typing import Dict, List, Optional, Union

logger = logging.getLogger(__name__)


@dataclass
class ProcessResult:
    """Result of a process execution."""

    code: int
    stdout: str
    stderr: str
    ok: bool = False
    details: str = ""

    def __post_init__(self):
        self.ok = self.code == 0
        if not self.details:
            self.details = self.stderr if self.stderr else "Process completed"


class ProcessRunner:
    """Execute external processes with proper error handling and dry-run support."""

    def __init__(self, dry_run: bool = False):
        """Initialize ProcessRunner.

        Args:
            dry_run: If True, commands will be logged but not executed
        """
        self.dry_run = dry_run
        self.logger = logging.getLogger(__name__)

    def run(
        self,
        command: Union[str, List[str]],
        cwd: Optional[str] = None,
        env: Optional[Dict[str, str]] = None,
        timeout: Optional[int] = None,
        capture_output: bool = True,
        text: bool = True,
        **kwargs,
    ) -> ProcessResult:
        """Run a command and return the result.

        Args:
            command: Command to execute (string or list)
            cwd: Working directory for the command
            env: Environment variables
            timeout: Timeout in seconds
            capture_output: Whether to capture stdout/stderr
            text: Whether to decode output as text
            **kwargs: Additional arguments for subprocess.run

        Returns:
            ProcessResult with execution details
        """
        # Convert string command to list if needed
        if isinstance(command, str):
            cmd_str = command
            # On Windows, we need shell=True for string commands
            kwargs.setdefault("shell", True)
        else:
            cmd_str = " ".join(command)
            command = command

        self.logger.info(f"{'[DRY RUN] ' if self.dry_run else ''}Running: {cmd_str}")

        if self.dry_run:
            return ProcessResult(
                code=0,
                stdout=f"[DRY RUN] Would execute: {cmd_str}",
                stderr="",
                ok=True,
                details="Dry run - command not executed",
            )

        try:
            result = subprocess.run(
                command,
                cwd=cwd,
                env=env,
                timeout=timeout,
                capture_output=capture_output,
                text=text,
                **kwargs,
            )

            return ProcessResult(
                code=result.returncode,
                stdout=result.stdout if capture_output else "",
                stderr=result.stderr if capture_output else "",
                ok=result.returncode == 0,
                details=result.stderr if result.returncode != 0 else "Success",
            )

        except subprocess.TimeoutExpired as e:
            return ProcessResult(
                code=-1,
                stdout=e.stdout.decode() if e.stdout else "",
                stderr=e.stderr.decode() if e.stderr else "",
                ok=False,
                details=f"Command timed out after {timeout} seconds",
            )

        except subprocess.CalledProcessError as e:
            return ProcessResult(
                code=e.returncode,
                stdout=e.stdout if e.stdout else "",
                stderr=e.stderr if e.stderr else "",
                ok=False,
                details=f"Command failed with exit code {e.returncode}",
            )

        except Exception as e:
            return ProcessResult(
                code=-1,
                stdout="",
                stderr=str(e),
                ok=False,
                details=f"Process execution failed: {str(e)}",
            )

    def check_tool_available(self, tool_name: str) -> bool:
        """Check if a tool is available in PATH.

        Args:
            tool_name: Name of the tool to check

        Returns:
            True if tool is available, False otherwise
        """
        try:
            result = self.run(
                f"where {tool_name}" if self._is_windows() else f"which {tool_name}",
                capture_output=True,
            )
            return result.ok
        except Exception:
            return False

    def get_tool_version(
        self, tool_name: str, version_arg: str = "--version"
    ) -> Optional[str]:
        """Get version information for a tool.

        Args:
            tool_name: Name of the tool
            version_arg: Argument to get version (default: --version)

        Returns:
            Version string if successful, None otherwise
        """
        try:
            result = self.run(f"{tool_name} {version_arg}", capture_output=True)
            if result.ok:
                return result.stdout.strip()
        except Exception:
            pass
        return None

    def _is_windows(self) -> bool:
        """Check if running on Windows."""
        import platform

        return platform.system().lower() == "windows"
