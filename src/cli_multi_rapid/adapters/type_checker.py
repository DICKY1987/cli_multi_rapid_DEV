#!/usr/bin/env python3
"""
Type Checker Adapter

Performs static type checking for multiple programming languages to ensure
type safety and catch type-related errors in the Codex pipeline.
"""

import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional

from .base_adapter import AdapterResult, AdapterType, BaseAdapter


class TypeCheckerAdapter(BaseAdapter):
    """Adapter for static type checking across multiple languages."""

    def __init__(self):
        super().__init__(
            name="type_checker",
            adapter_type=AdapterType.DETERMINISTIC,
            description="Perform static type checking for multiple programming languages",
        )

    def execute(
        self,
        step: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None,
        files: Optional[str] = None,
    ) -> AdapterResult:
        """Execute type checking."""
        self._log_execution_start(step)

        try:
            with_params = self._extract_with_params(step)
            target_files = with_params.get("target_files", [])
            languages = with_params.get("languages", ["python"])
            strict_mode = with_params.get("strict_mode", False)
            ignore_missing_imports = with_params.get("ignore_missing_imports", True)

            if not target_files:
                return AdapterResult(
                    success=False,
                    error="Missing required parameter: target_files"
                )

            type_check_results = {
                "check_timestamp": self._get_timestamp(),
                "target_files": target_files,
                "languages": languages,
                "strict_mode": strict_mode,
                "ignore_missing_imports": ignore_missing_imports,
                "file_results": [],
                "summary": {
                    "total_files": 0,
                    "files_checked": 0,
                    "files_with_errors": 0,
                    "total_errors": 0,
                    "total_warnings": 0
                }
            }

            # Check each file
            for file_path in target_files:
                file_result = self._check_file_types(file_path, languages, strict_mode, ignore_missing_imports)
                type_check_results["file_results"].append(file_result)

                type_check_results["summary"]["total_files"] += 1
                if file_result.get("checked", False):
                    type_check_results["summary"]["files_checked"] += 1

                errors = file_result.get("errors", [])
                warnings = file_result.get("warnings", [])

                if errors:
                    type_check_results["summary"]["files_with_errors"] += 1

                type_check_results["summary"]["total_errors"] += len(errors)
                type_check_results["summary"]["total_warnings"] += len(warnings)

            # Determine overall success
            overall_success = type_check_results["summary"]["total_errors"] == 0

            # Write type check results
            emit_paths = self._extract_emit_paths(step)
            artifacts = []

            if emit_paths:
                for emit_path in emit_paths:
                    artifact_path = Path(emit_path)
                    artifact_path.parent.mkdir(parents=True, exist_ok=True)

                    with open(artifact_path, 'w', encoding='utf-8') as f:
                        import json
                        json.dump(type_check_results, f, indent=2)

                    artifacts.append(str(artifact_path))
                    self.logger.info(f"Type check results written to: {artifact_path}")

            result = AdapterResult(
                success=overall_success,
                tokens_used=0,  # Deterministic operation
                artifacts=artifacts,
                output=f"Type checked {type_check_results['summary']['files_checked']} files, found {type_check_results['summary']['total_errors']} errors and {type_check_results['summary']['total_warnings']} warnings",
                metadata=type_check_results
            )

            self._log_execution_complete(result)
            return result

        except Exception as e:
            error_msg = f"Type checking failed: {str(e)}"
            self.logger.error(error_msg)
            return AdapterResult(
                success=False,
                error=error_msg,
                metadata={"exception_type": type(e).__name__}
            )

    def validate_step(self, step: Dict[str, Any]) -> bool:
        """Validate that this adapter can execute the given step."""
        with_params = self._extract_with_params(step)
        return "target_files" in with_params

    def estimate_cost(self, step: Dict[str, Any]) -> int:
        """Estimate token cost (0 for deterministic operations)."""
        return 0

    def is_available(self) -> bool:
        """Check if required type checkers are available."""
        # Check for mypy (Python type checker)
        try:
            result = subprocess.run(
                ["mypy", "--version"],
                capture_output=True,
                text=True,
                timeout=5
            )
            return result.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return False

    def _check_file_types(self, file_path: str, languages: List[str], strict_mode: bool, ignore_missing_imports: bool) -> Dict[str, Any]:
        """Check types for a single file."""
        file_result = {
            "file_path": file_path,
            "language": None,
            "checked": False,
            "errors": [],
            "warnings": [],
            "info": []
        }

        try:
            target_file = Path(file_path)

            if not target_file.exists():
                file_result["errors"].append({
                    "type": "FileNotFound",
                    "message": f"File not found: {file_path}"
                })
                return file_result

            # Determine language
            language = self._detect_language(target_file)
            file_result["language"] = language

            # Type check based on language
            if language == "python" and ("python" in languages or "auto" in languages):
                self._check_python_types(target_file, file_result, strict_mode, ignore_missing_imports)
            elif language == "typescript" and ("typescript" in languages or "auto" in languages):
                self._check_typescript_types(target_file, file_result, strict_mode)
            elif language == "javascript" and ("javascript" in languages or "auto" in languages):
                # JavaScript doesn't have built-in type checking, but we can suggest TypeScript
                file_result["info"].append({
                    "type": "Suggestion",
                    "message": "Consider using TypeScript for static type checking"
                })
                file_result["checked"] = True
            else:
                file_result["info"].append({
                    "type": "UnsupportedLanguage",
                    "message": f"Type checking not supported for language: {language}"
                })

        except Exception as e:
            file_result["errors"].append({
                "type": "CheckException",
                "message": f"Type check exception: {str(e)}"
            })

        return file_result

    def _detect_language(self, file_path: Path) -> str:
        """Detect programming language from file extension."""
        extension = file_path.suffix.lower()

        language_map = {
            ".py": "python",
            ".pyi": "python",
            ".js": "javascript",
            ".jsx": "javascript",
            ".ts": "typescript",
            ".tsx": "typescript"
        }

        return language_map.get(extension, "unknown")

    def _check_python_types(self, file_path: Path, result: Dict[str, Any], strict_mode: bool, ignore_missing_imports: bool) -> None:
        """Check Python types using mypy."""
        try:
            # Build mypy command
            cmd = ["mypy"]

            if strict_mode:
                cmd.append("--strict")
            else:
                # Standard type checking options
                cmd.extend([
                    "--check-untyped-defs",
                    "--disallow-untyped-calls",
                    "--disallow-incomplete-defs"
                ])

            if ignore_missing_imports:
                cmd.append("--ignore-missing-imports")

            # Add other useful options
            cmd.extend([
                "--show-error-codes",
                "--show-column-numbers",
                "--no-error-summary",
                str(file_path)
            ])

            # Run mypy
            mypy_result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60
            )

            result["checked"] = True

            if mypy_result.returncode == 0:
                # No type errors
                result["info"].append({
                    "type": "Success",
                    "message": "No type errors found"
                })
            else:
                # Parse mypy output
                self._parse_mypy_output(mypy_result.stdout, result)

        except subprocess.TimeoutExpired:
            result["errors"].append({
                "type": "Timeout",
                "message": "Type checking timed out"
            })
        except FileNotFoundError:
            result["errors"].append({
                "type": "ToolNotFound",
                "message": "mypy not found - install with: pip install mypy"
            })
        except Exception as e:
            result["errors"].append({
                "type": "MypyException",
                "message": f"mypy execution failed: {str(e)}"
            })

    def _parse_mypy_output(self, output: str, result: Dict[str, Any]) -> None:
        """Parse mypy output into structured errors and warnings."""
        lines = output.strip().split('\n')

        for line in lines:
            if not line.strip():
                continue

            # Parse mypy output format: file:line:col: error_type: message [error_code]
            parts = line.split(':', 4)
            if len(parts) >= 4:
                try:
                    file_path = parts[0]
                    line_num = int(parts[1])
                    col_num = int(parts[2]) if parts[2].isdigit() else None
                    severity_and_message = parts[3].strip()

                    # Extract error code if present
                    error_code = None
                    if '[' in severity_and_message and ']' in severity_and_message:
                        code_start = severity_and_message.rfind('[')
                        code_end = severity_and_message.rfind(']')
                        error_code = severity_and_message[code_start+1:code_end]
                        severity_and_message = severity_and_message[:code_start].strip()

                    # Determine severity
                    if severity_and_message.startswith('error'):
                        severity = 'error'
                        message = severity_and_message[6:].strip()
                    elif severity_and_message.startswith('warning'):
                        severity = 'warning'
                        message = severity_and_message[8:].strip()
                    elif severity_and_message.startswith('note'):
                        severity = 'info'
                        message = severity_and_message[5:].strip()
                    else:
                        severity = 'error'
                        message = severity_and_message

                    issue = {
                        "type": "MyPyIssue",
                        "severity": severity,
                        "message": message,
                        "line": line_num,
                        "column": col_num,
                        "error_code": error_code
                    }

                    if severity == 'error':
                        result["errors"].append(issue)
                    elif severity == 'warning':
                        result["warnings"].append(issue)
                    else:
                        result["info"].append(issue)

                except (ValueError, IndexError):
                    # Fallback for unparseable lines
                    result["info"].append({
                        "type": "UnparsedOutput",
                        "message": line.strip()
                    })

    def _check_typescript_types(self, file_path: Path, result: Dict[str, Any], strict_mode: bool) -> None:
        """Check TypeScript types using tsc."""
        try:
            # Build TypeScript compiler command
            cmd = ["tsc", "--noEmit", "--skipLibCheck"]

            if strict_mode:
                cmd.append("--strict")

            cmd.append(str(file_path))

            # Run TypeScript compiler
            tsc_result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60
            )

            result["checked"] = True

            if tsc_result.returncode == 0:
                result["info"].append({
                    "type": "Success",
                    "message": "No type errors found"
                })
            else:
                # Parse TypeScript compiler output
                self._parse_tsc_output(tsc_result.stdout, result)

        except subprocess.TimeoutExpired:
            result["errors"].append({
                "type": "Timeout",
                "message": "TypeScript type checking timed out"
            })
        except FileNotFoundError:
            result["errors"].append({
                "type": "ToolNotFound",
                "message": "tsc not found - install TypeScript with: npm install -g typescript"
            })
        except Exception as e:
            result["errors"].append({
                "type": "TscException",
                "message": f"tsc execution failed: {str(e)}"
            })

    def _parse_tsc_output(self, output: str, result: Dict[str, Any]) -> None:
        """Parse TypeScript compiler output into structured errors and warnings."""
        lines = output.strip().split('\n')

        for line in lines:
            if not line.strip():
                continue

            # Parse tsc output format: file(line,col): error TS####: message
            if '(' in line and ')' in line and ': error TS' in line:
                try:
                    # Extract file path
                    file_part = line.split('(')[0]

                    # Extract line and column
                    coords_part = line.split('(')[1].split(')')[0]
                    if ',' in coords_part:
                        line_num, col_num = coords_part.split(',')
                        line_num = int(line_num)
                        col_num = int(col_num)
                    else:
                        line_num = int(coords_part)
                        col_num = None

                    # Extract error code and message
                    error_part = line.split(': error TS')[1]
                    error_code = error_part.split(':')[0]
                    message = ':'.join(error_part.split(':')[1:]).strip()

                    issue = {
                        "type": "TypeScriptError",
                        "message": message,
                        "line": line_num,
                        "column": col_num,
                        "error_code": f"TS{error_code}"
                    }

                    result["errors"].append(issue)

                except (ValueError, IndexError):
                    # Fallback for unparseable lines
                    result["info"].append({
                        "type": "UnparsedOutput",
                        "message": line.strip()
                    })
            else:
                # Handle other output lines
                result["info"].append({
                    "type": "CompilerOutput",
                    "message": line.strip()
                })

    def _get_timestamp(self) -> str:
        """Get current timestamp in ISO format."""
        from datetime import datetime
        return datetime.utcnow().isoformat() + "Z"
