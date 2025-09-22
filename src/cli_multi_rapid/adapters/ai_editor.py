#!/usr/bin/env python3
"""
AI Editor Adapter

Integrates AI-powered code editing tools like aider for intelligent code modifications.
Supports multiple AI backends (Claude, GPT, Gemini) with cost tracking and safety gates.
"""

import json
import logging
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Optional

from .base_adapter import AdapterResult, AdapterType, BaseAdapter

logger = logging.getLogger(__name__)


class AIEditorAdapter(BaseAdapter):
    """AI-powered code editing adapter using aider and other AI tools."""

    def __init__(self):
        super().__init__(
            name="ai_editor",
            adapter_type=AdapterType.AI,
            description="AI-powered code editing with aider integration",
        )

    def execute(
        self,
        step: dict[str, Any],
        context: Optional[dict[str, Any]] = None,
        files: Optional[str] = None,
    ) -> AdapterResult:
        """Execute AI editing workflow step."""
        self._log_execution_start(step)

        try:
            # Extract parameters
            with_params = self._extract_with_params(step)
            emit_paths = self._extract_emit_paths(step)

            # Get AI tool and operation
            tool = with_params.get("tool", "aider")
            operation = with_params.get("operation", "edit")
            prompt = with_params.get("prompt", "")
            model = with_params.get("model", "claude-3-5-sonnet-20241022")
            max_tokens = with_params.get("max_tokens", 4000)

            if not prompt:
                return AdapterResult(
                    success=False,
                    error="AI editor requires 'prompt' parameter",
                )

            # Execute AI editing based on tool
            if tool == "aider":
                result = self._execute_aider_edit(
                    files=files,
                    prompt=prompt,
                    model=model,
                    max_tokens=max_tokens,
                    operation=operation,
                    emit_paths=emit_paths,
                )
            elif tool == "claude_direct":
                result = self._execute_claude_direct(
                    files=files,
                    prompt=prompt,
                    model=model,
                    max_tokens=max_tokens,
                    emit_paths=emit_paths,
                )
            else:
                return AdapterResult(
                    success=False,
                    error=f"Unsupported AI tool: {tool}",
                )

            self._log_execution_complete(result)
            return result

        except Exception as e:
            error_msg = f"AI editing failed: {str(e)}"
            logger.error(error_msg)
            return AdapterResult(success=False, error=error_msg)

    def _execute_aider_edit(
        self,
        files: Optional[str],
        prompt: str,
        model: str,
        max_tokens: int,
        operation: str,
        emit_paths: list[str],
    ) -> AdapterResult:
        """Execute aider-based AI editing."""

        # Build aider command
        cmd = [
            "aider",
            "--model",
            model,
            "--no-git",  # Don't auto-commit
            "--yes",  # Auto-confirm
            "--quiet",  # Reduce output
        ]

        # Add files to edit
        if files:
            # Convert glob pattern to actual files
            file_list = self._resolve_file_pattern(files)
            if not file_list:
                return AdapterResult(
                    success=False,
                    error=f"No files found matching pattern: {files}",
                )
            cmd.extend(file_list)

        # Create temporary file for the prompt
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".txt", delete=False
        ) as prompt_file:
            prompt_file.write(prompt)
            prompt_file_path = prompt_file.name

        try:
            # Execute aider with the prompt
            process = subprocess.run(
                cmd + ["--message", prompt],
                capture_output=True,
                text=True,
                timeout=300,  # 5 minute timeout
            )

            # Parse aider output
            tokens_used = self._extract_tokens_from_aider_output(process.stdout)

            if process.returncode == 0:
                # Generate diff artifact
                artifacts = self._generate_diff_artifacts(
                    emit_paths, file_list if files else []
                )

                return AdapterResult(
                    success=True,
                    tokens_used=tokens_used,
                    artifacts=artifacts,
                    output=process.stdout,
                    metadata={
                        "tool": "aider",
                        "model": model,
                        "files_modified": len(file_list) if files else 0,
                        "prompt_length": len(prompt),
                    },
                )
            else:
                return AdapterResult(
                    success=False,
                    error=f"Aider failed: {process.stderr}",
                    output=process.stdout,
                )

        finally:
            # Clean up prompt file
            Path(prompt_file_path).unlink(missing_ok=True)

    def _execute_claude_direct(
        self,
        files: Optional[str],
        prompt: str,
        model: str,
        max_tokens: int,
        emit_paths: list[str],
    ) -> AdapterResult:
        """Execute direct Claude API integration (placeholder for future implementation)."""

        # This would integrate directly with Anthropic's API
        # For now, return a helpful error suggesting to use aider
        return AdapterResult(
            success=False,
            error="Direct Claude integration not yet implemented. Use 'aider' tool instead.",
            metadata={
                "suggestion": "Use 'tool: aider' with 'model: claude-3-5-sonnet-20241022'",
            },
        )

    def _resolve_file_pattern(self, pattern: str) -> list[str]:
        """Resolve glob pattern to list of actual files."""
        try:
            from glob import glob

            files = glob(pattern, recursive=True)
            # Filter to only Python files for safety
            return [
                f
                for f in files
                if f.endswith((".py", ".ts", ".js", ".md", ".yaml", ".yml"))
            ]
        except Exception as e:
            logger.warning(f"Failed to resolve file pattern {pattern}: {e}")
            return []

    def _extract_tokens_from_aider_output(self, output: str) -> int:
        """Extract token usage from aider output."""
        # Aider typically shows token usage in its output
        # Look for patterns like "Tokens: 1234"
        import re

        patterns = [
            r"Tokens:\s*(\d+)",
            r"(\d+)\s*tokens",
            r"Token usage:\s*(\d+)",
        ]

        for pattern in patterns:
            match = re.search(pattern, output, re.IGNORECASE)
            if match:
                return int(match.group(1))

        # Estimate tokens if not found (rough approximation)
        return len(output.split()) * 1.3  # Conservative estimate

    def _generate_diff_artifacts(
        self, emit_paths: list[str], modified_files: list[str]
    ) -> list[str]:
        """Generate diff artifacts for modified files."""
        artifacts = []

        for emit_path in emit_paths:
            try:
                # Generate git diff for the modified files
                if modified_files:
                    diff_result = subprocess.run(
                        ["git", "diff", "--no-color"] + modified_files,
                        capture_output=True,
                        text=True,
                    )

                    if diff_result.returncode == 0:
                        # Save diff to artifact file
                        Path(emit_path).parent.mkdir(parents=True, exist_ok=True)

                        diff_data = {
                            "type": "ai_edit_diff",
                            "files_modified": modified_files,
                            "diff": diff_result.stdout,
                            "timestamp": self._get_timestamp(),
                        }

                        with open(emit_path, "w") as f:
                            json.dump(diff_data, f, indent=2)

                        artifacts.append(emit_path)

            except Exception as e:
                logger.warning(f"Failed to generate diff artifact {emit_path}: {e}")

        return artifacts

    def _get_timestamp(self) -> str:
        """Get current timestamp in ISO format."""
        from datetime import datetime

        return datetime.now().isoformat()

    def validate_step(self, step: dict[str, Any]) -> bool:
        """Validate that this adapter can execute the given step."""
        with_params = self._extract_with_params(step)

        # Check required parameters
        if "prompt" not in with_params:
            return False

        # Check supported tools
        tool = with_params.get("tool", "aider")
        supported_tools = ["aider", "claude_direct"]

        return tool in supported_tools

    def estimate_cost(self, step: dict[str, Any]) -> int:
        """Estimate token cost for AI editing operation."""
        with_params = self._extract_with_params(step)

        # Base cost for the prompt
        prompt = with_params.get("prompt", "")
        base_tokens = len(prompt.split()) * 1.3  # Conservative token estimate

        # Add estimated tokens for file content
        max_tokens = with_params.get("max_tokens", 4000)

        # AI editing typically uses 2-3x the input tokens for output
        estimated_total = base_tokens + max_tokens * 2

        return int(estimated_total)

    def is_available(self) -> bool:
        """Check if aider or other AI tools are available."""
        try:
            # Check if aider is installed
            result = subprocess.run(
                ["aider", "--version"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            return result.returncode == 0
        except Exception:
            # If aider isn't available, we could still use direct API integration
            # For now, require aider
            return False

    def get_supported_models(self) -> list[str]:
        """Get list of supported AI models."""
        return [
            "claude-3-5-sonnet-20241022",
            "claude-3-opus-20240229",
            "gpt-4-turbo-preview",
            "gpt-4",
            "gemini-1.5-pro",
        ]

    def get_supported_operations(self) -> list[str]:
        """Get list of supported editing operations."""
        return [
            "edit",  # General editing
            "refactor",  # Code refactoring
            "fix",  # Bug fixing
            "optimize",  # Performance optimization
            "document",  # Add documentation
            "test",  # Add tests
        ]
