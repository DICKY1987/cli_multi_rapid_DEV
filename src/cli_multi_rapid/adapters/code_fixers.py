#!/usr/bin/env python3
"""
Code Fixers Adapter

Integrates with Python code formatting and linting tools:
- ruff: Fast Python linter and formatter
- black: Code formatter
- isort: Import sorter

Executes deterministic code fixes and reports the results.
"""

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional

from .base_adapter import AdapterResult, AdapterType, BaseAdapter


class CodeFixersAdapter(BaseAdapter):
    """Adapter for automated code fixing tools."""

    def __init__(self):
        super().__init__(
            name="code_fixers",
            adapter_type=AdapterType.DETERMINISTIC,
            description="Apply automated code fixes (ruff, black, isort)",
        )
        self._available_tools = self._check_available_tools()

    def _check_available_tools(self) -> Dict[str, bool]:
        """Check which code fixing tools are available."""
        tools = {}
        for tool in ["ruff", "black", "isort"]:
            tools[tool] = shutil.which(tool) is not None
            if tools[tool]:
                self.logger.debug(f"Found {tool}: {shutil.which(tool)}")
            else:
                self.logger.warning(f"{tool} not found in PATH")
        return tools

    def is_available(self) -> bool:
        """Check if at least one code fixing tool is available."""
        return any(self._available_tools.values())

    def validate_step(self, step: Dict[str, Any]) -> bool:
        """Validate that this adapter can execute the given step."""
        # Must have at least one tool available
        if not self.is_available():
            return False

        # Check if requested tools are available
        with_params = self._extract_with_params(step)
        requested_tools = with_params.get("tools", ["ruff", "black", "isort"])

        return any(self._available_tools.get(tool, False) for tool in requested_tools)

    def estimate_cost(self, step: Dict[str, Any]) -> int:
        """Estimate token cost (0 for deterministic tools)."""
        return 0

    def execute(
        self,
        step: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None,
        files: Optional[str] = None,
    ) -> AdapterResult:
        """Execute code fixing tools on the specified files."""
        self._log_execution_start(step)

        with_params = self._extract_with_params(step)
        emit_paths = self._extract_emit_paths(step)

        # Determine which tools to run
        requested_tools = with_params.get("tools", ["ruff", "black", "isort"])
        fix_mode = with_params.get("fix", True)  # Whether to apply fixes or just check

        # Determine target files
        if not files:
            files = with_params.get("files", "**/*.py")

        # Convert glob pattern to actual file list
        target_files = self._resolve_file_pattern(files)
        if not target_files:
            return AdapterResult(
                success=True,
                output="No Python files found to process",
                artifacts=emit_paths,
            )

        results = {}
        total_fixes = 0
        errors = []

        # Run each requested tool
        for tool in requested_tools:
            if not self._available_tools.get(tool, False):
                self.logger.warning(f"Skipping {tool}: not available")
                continue

            try:
                tool_result = self._run_tool(tool, target_files, fix_mode)
                results[tool] = tool_result
                total_fixes += tool_result.get("fixes_applied", 0)

                if tool_result.get("error"):
                    errors.append(f"{tool}: {tool_result['error']}")

            except Exception as e:
                error_msg = f"Failed to run {tool}: {e}"
                self.logger.error(error_msg)
                errors.append(error_msg)

        # Generate artifacts
        artifacts = self._generate_artifacts(emit_paths, results, target_files)

        # Determine success
        success = len(errors) == 0
        output = self._format_output(results, total_fixes, len(target_files))
        error = "; ".join(errors) if errors else None

        result = AdapterResult(
            success=success,
            output=output,
            error=error,
            artifacts=artifacts,
            metadata={
                "tools_run": list(results.keys()),
                "files_processed": len(target_files),
                "total_fixes": total_fixes,
                "results": results,
            },
        )

        self._log_execution_complete(result)
        return result

    def _resolve_file_pattern(self, pattern: str) -> List[Path]:
        """Resolve file pattern to list of Python files."""
        try:
            # Use pathlib to resolve glob patterns
            current_dir = Path(".")
            if "**" in pattern:
                files = list(current_dir.glob(pattern))
            else:
                files = list(current_dir.glob(pattern))

            # Filter to only Python files
            python_files = [f for f in files if f.suffix == ".py" and f.is_file()]
            self.logger.debug(f"Resolved {pattern} to {len(python_files)} Python files")
            return python_files

        except Exception as e:
            self.logger.error(f"Failed to resolve file pattern {pattern}: {e}")
            return []

    def _run_tool(self, tool: str, files: List[Path], fix_mode: bool) -> Dict[str, Any]:
        """Run a specific code fixing tool."""
        file_paths = [str(f) for f in files]

        if tool == "ruff":
            return self._run_ruff(file_paths, fix_mode)
        elif tool == "black":
            return self._run_black(file_paths, fix_mode)
        elif tool == "isort":
            return self._run_isort(file_paths, fix_mode)
        else:
            return {"error": f"Unknown tool: {tool}"}

    def _run_ruff(self, files: List[str], fix_mode: bool) -> Dict[str, Any]:
        """Run ruff linter/formatter."""
        try:
            if fix_mode:
                cmd = ["ruff", "check", "--fix"] + files
            else:
                cmd = ["ruff", "check"] + files

            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)

            return {
                "exit_code": result.returncode,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "fixes_applied": result.stdout.count("Fixed ") if fix_mode else 0,
                "error": result.stderr if result.returncode != 0 else None,
            }
        except subprocess.TimeoutExpired:
            return {"error": "ruff execution timed out"}
        except Exception as e:
            return {"error": str(e)}

    def _run_black(self, files: List[str], fix_mode: bool) -> Dict[str, Any]:
        """Run black formatter."""
        try:
            if fix_mode:
                cmd = ["black"] + files
            else:
                cmd = ["black", "--check", "--diff"] + files

            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)

            # Black exit codes: 0 = no changes, 1 = changes made/needed
            fixes_applied = 0
            if fix_mode and result.returncode == 0:
                # Count "reformatted" in stdout
                fixes_applied = result.stdout.count("reformatted ")

            return {
                "exit_code": result.returncode,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "fixes_applied": fixes_applied,
                "error": result.stderr if result.returncode > 1 else None,
            }
        except subprocess.TimeoutExpired:
            return {"error": "black execution timed out"}
        except Exception as e:
            return {"error": str(e)}

    def _run_isort(self, files: List[str], fix_mode: bool) -> Dict[str, Any]:
        """Run isort import sorter."""
        try:
            if fix_mode:
                cmd = ["isort"] + files
            else:
                cmd = ["isort", "--check-only", "--diff"] + files

            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)

            # isort exit codes: 0 = no changes, 1 = changes made/needed
            fixes_applied = 0
            if fix_mode and "Fixing " in result.stdout:
                fixes_applied = result.stdout.count("Fixing ")

            return {
                "exit_code": result.returncode,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "fixes_applied": fixes_applied,
                "error": result.stderr if result.returncode > 1 else None,
            }
        except subprocess.TimeoutExpired:
            return {"error": "isort execution timed out"}
        except Exception as e:
            return {"error": str(e)}

    def _generate_artifacts(
        self, emit_paths: List[str], results: Dict[str, Any], files: List[Path]
    ) -> List[str]:
        """Generate artifact files with tool results."""
        artifacts = []

        for emit_path in emit_paths:
            try:
                artifact_data = {
                    "adapter": "code_fixers",
                    "timestamp": "2025-09-20T12:00:00Z",  # Would be actual timestamp
                    "files_processed": [str(f) for f in files],
                    "results": results,
                    "summary": {
                        "total_tools": len(results),
                        "total_fixes": sum(
                            r.get("fixes_applied", 0) for r in results.values()
                        ),
                        "errors": [
                            r.get("error") for r in results.values() if r.get("error")
                        ],
                    },
                }

                # Ensure directory exists
                Path(emit_path).parent.mkdir(parents=True, exist_ok=True)

                # Write artifact
                with open(emit_path, "w") as f:
                    json.dump(artifact_data, f, indent=2)

                artifacts.append(emit_path)
                self.logger.debug(f"Generated artifact: {emit_path}")

            except Exception as e:
                self.logger.error(f"Failed to generate artifact {emit_path}: {e}")

        return artifacts

    def _format_output(
        self, results: Dict[str, Any], total_fixes: int, file_count: int
    ) -> str:
        """Format human-readable output summary."""
        lines = [
            f"Code Fixers Results: {file_count} files processed",
            f"Total fixes applied: {total_fixes}",
            "",
        ]

        for tool, result in results.items():
            status = "OK" if not result.get("error") else "FAIL"
            fixes = result.get("fixes_applied", 0)
            lines.append(f"{status} {tool}: {fixes} fixes")

            if result.get("error"):
                lines.append(f"   Error: {result['error']}")

        return "\n".join(lines)