#!/usr/bin/env python3
"""
Syntax Validator Adapter

Validates code syntax for multiple programming languages to ensure
modifications don't introduce syntax errors in the Codex pipeline.
"""

import ast
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional

from .base_adapter import AdapterResult, AdapterType, BaseAdapter


class SyntaxValidatorAdapter(BaseAdapter):
    """Adapter for validating code syntax across multiple languages."""

    def __init__(self):
        super().__init__(
            name="syntax_validator",
            adapter_type=AdapterType.DETERMINISTIC,
            description="Validate code syntax for multiple programming languages",
        )

    def execute(
        self,
        step: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None,
        files: Optional[str] = None,
    ) -> AdapterResult:
        """Execute syntax validation."""
        self._log_execution_start(step)

        try:
            with_params = self._extract_with_params(step)
            target_files = with_params.get("target_files", [])
            languages = with_params.get("languages", ["python"])
            fail_fast = with_params.get("fail_fast", True)

            if not target_files:
                return AdapterResult(
                    success=False,
                    error="Missing required parameter: target_files"
                )

            validation_results = {
                "validation_timestamp": self._get_timestamp(),
                "target_files": target_files,
                "languages": languages,
                "fail_fast": fail_fast,
                "file_validations": [],
                "summary": {
                    "total_files": 0,
                    "valid_files": 0,
                    "invalid_files": 0,
                    "error_count": 0
                }
            }

            # Validate each file
            for file_path in target_files:
                file_validation = self._validate_file_syntax(file_path, languages)
                validation_results["file_validations"].append(file_validation)

                validation_results["summary"]["total_files"] += 1
                if file_validation["valid"]:
                    validation_results["summary"]["valid_files"] += 1
                else:
                    validation_results["summary"]["invalid_files"] += 1
                    validation_results["summary"]["error_count"] += len(file_validation.get("errors", []))

                # Fail fast if requested and validation failed
                if fail_fast and not file_validation["valid"]:
                    validation_results["failed_fast"] = True
                    break

            # Determine overall success
            overall_success = validation_results["summary"]["invalid_files"] == 0

            # Write validation results
            emit_paths = self._extract_emit_paths(step)
            artifacts = []

            if emit_paths:
                for emit_path in emit_paths:
                    artifact_path = Path(emit_path)
                    artifact_path.parent.mkdir(parents=True, exist_ok=True)

                    with open(artifact_path, 'w', encoding='utf-8') as f:
                        import json
                        json.dump(validation_results, f, indent=2)

                    artifacts.append(str(artifact_path))
                    self.logger.info(f"Syntax validation results written to: {artifact_path}")

            result = AdapterResult(
                success=overall_success,
                tokens_used=0,  # Deterministic operation
                artifacts=artifacts,
                output=f"Validated {validation_results['summary']['total_files']} files, {validation_results['summary']['valid_files']} valid, {validation_results['summary']['invalid_files']} invalid",
                metadata=validation_results
            )

            self._log_execution_complete(result)
            return result

        except Exception as e:
            error_msg = f"Syntax validation failed: {str(e)}"
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
        """Check if required tools are available."""
        # Basic availability check - Python AST parsing is always available
        return True

    def _validate_file_syntax(self, file_path: str, languages: List[str]) -> Dict[str, Any]:
        """Validate syntax for a single file."""
        file_validation = {
            "file_path": file_path,
            "valid": True,
            "language": None,
            "errors": [],
            "warnings": []
        }

        try:
            target_file = Path(file_path)

            if not target_file.exists():
                file_validation["valid"] = False
                file_validation["errors"].append(f"File not found: {file_path}")
                return file_validation

            if not target_file.is_file():
                file_validation["valid"] = False
                file_validation["errors"].append(f"Path is not a file: {file_path}")
                return file_validation

            # Determine language from file extension
            language = self._detect_language(target_file)
            file_validation["language"] = language

            # Validate based on detected language
            if language == "python" and ("python" in languages or "auto" in languages):
                self._validate_python_syntax(target_file, file_validation)
            elif language == "javascript" and ("javascript" in languages or "auto" in languages):
                self._validate_javascript_syntax(target_file, file_validation)
            elif language == "typescript" and ("typescript" in languages or "auto" in languages):
                self._validate_typescript_syntax(target_file, file_validation)
            elif language == "json" and ("json" in languages or "auto" in languages):
                self._validate_json_syntax(target_file, file_validation)
            elif language == "yaml" and ("yaml" in languages or "auto" in languages):
                self._validate_yaml_syntax(target_file, file_validation)
            else:
                file_validation["warnings"].append(f"Unsupported language: {language}")

        except Exception as e:
            file_validation["valid"] = False
            file_validation["errors"].append(f"Validation exception: {str(e)}")

        return file_validation

    def _detect_language(self, file_path: Path) -> str:
        """Detect programming language from file extension."""
        extension = file_path.suffix.lower()

        language_map = {
            ".py": "python",
            ".js": "javascript",
            ".jsx": "javascript",
            ".ts": "typescript",
            ".tsx": "typescript",
            ".json": "json",
            ".yaml": "yaml",
            ".yml": "yaml",
            ".md": "markdown",
            ".sh": "shell",
            ".bash": "shell",
            ".bat": "batch",
            ".ps1": "powershell"
        }

        return language_map.get(extension, "unknown")

    def _validate_python_syntax(self, file_path: Path, validation: Dict[str, Any]) -> None:
        """Validate Python syntax using AST."""
        try:
            with open(file_path, encoding='utf-8') as f:
                source_code = f.read()

            # Try to parse the AST
            ast.parse(source_code, filename=str(file_path))

        except SyntaxError as e:
            validation["valid"] = False
            validation["errors"].append({
                "type": "SyntaxError",
                "message": str(e.msg),
                "line": e.lineno,
                "column": e.offset,
                "text": e.text.strip() if e.text else None
            })
        except Exception as e:
            validation["valid"] = False
            validation["errors"].append({
                "type": "ParseError",
                "message": str(e)
            })

    def _validate_javascript_syntax(self, file_path: Path, validation: Dict[str, Any]) -> None:
        """Validate JavaScript syntax using Node.js."""
        try:
            # Try to validate with Node.js if available
            result = subprocess.run(
                ["node", "-c", str(file_path)],
                capture_output=True,
                text=True,
                timeout=30
            )

            if result.returncode != 0:
                validation["valid"] = False
                validation["errors"].append({
                    "type": "JavaScriptSyntaxError",
                    "message": result.stderr.strip()
                })

        except (subprocess.TimeoutExpired, FileNotFoundError):
            # Fallback: basic bracket/quote matching
            self._basic_syntax_check(file_path, validation, "javascript")

    def _validate_typescript_syntax(self, file_path: Path, validation: Dict[str, Any]) -> None:
        """Validate TypeScript syntax using tsc."""
        try:
            # Try to validate with TypeScript compiler if available
            result = subprocess.run(
                ["tsc", "--noEmit", "--skipLibCheck", str(file_path)],
                capture_output=True,
                text=True,
                timeout=30
            )

            if result.returncode != 0:
                validation["valid"] = False
                validation["errors"].append({
                    "type": "TypeScriptError",
                    "message": result.stderr.strip()
                })

        except (subprocess.TimeoutExpired, FileNotFoundError):
            # Fallback to JavaScript validation
            self._validate_javascript_syntax(file_path, validation)

    def _validate_json_syntax(self, file_path: Path, validation: Dict[str, Any]) -> None:
        """Validate JSON syntax."""
        try:
            import json
            with open(file_path, encoding='utf-8') as f:
                json.load(f)

        except json.JSONDecodeError as e:
            validation["valid"] = False
            validation["errors"].append({
                "type": "JSONDecodeError",
                "message": e.msg,
                "line": e.lineno,
                "column": e.colno
            })
        except Exception as e:
            validation["valid"] = False
            validation["errors"].append({
                "type": "JSONError",
                "message": str(e)
            })

    def _validate_yaml_syntax(self, file_path: Path, validation: Dict[str, Any]) -> None:
        """Validate YAML syntax."""
        try:
            import yaml
            with open(file_path, encoding='utf-8') as f:
                yaml.safe_load(f)

        except yaml.YAMLError as e:
            validation["valid"] = False
            validation["errors"].append({
                "type": "YAMLError",
                "message": str(e)
            })
        except Exception as e:
            validation["valid"] = False
            validation["errors"].append({
                "type": "YAMLParseError",
                "message": str(e)
            })

    def _basic_syntax_check(self, file_path: Path, validation: Dict[str, Any], language: str) -> None:
        """Perform basic syntax validation for unsupported languages."""
        try:
            with open(file_path, encoding='utf-8') as f:
                content = f.read()

            # Basic bracket/brace matching
            brackets = {'(': ')', '[': ']', '{': '}'}
            stack = []

            for i, char in enumerate(content):
                if char in brackets:
                    stack.append((char, i))
                elif char in brackets.values():
                    if not stack:
                        validation["valid"] = False
                        validation["errors"].append({
                            "type": "UnmatchedBracket",
                            "message": f"Unmatched closing bracket '{char}' at position {i}"
                        })
                        return

                    open_char, _ = stack.pop()
                    if brackets[open_char] != char:
                        validation["valid"] = False
                        validation["errors"].append({
                            "type": "MismatchedBracket",
                            "message": f"Mismatched bracket: expected '{brackets[open_char]}' but found '{char}' at position {i}"
                        })
                        return

            if stack:
                open_char, pos = stack[-1]
                validation["valid"] = False
                validation["errors"].append({
                    "type": "UnclosedBracket",
                    "message": f"Unclosed bracket '{open_char}' at position {pos}"
                })

        except Exception as e:
            validation["warnings"].append(f"Basic syntax check failed: {str(e)}")

    def _get_timestamp(self) -> str:
        """Get current timestamp in ISO format."""
        from datetime import datetime
        return datetime.utcnow().isoformat() + "Z"
