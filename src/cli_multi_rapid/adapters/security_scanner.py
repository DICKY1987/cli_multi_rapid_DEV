#!/usr/bin/env python3
"""
Security Scanner Adapter

Performs security analysis and vulnerability scanning for code to identify
potential security issues, insecure patterns, and compliance violations.
"""

import ast
import re
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional

from .base_adapter import AdapterResult, AdapterType, BaseAdapter


class SecurityScannerAdapter(BaseAdapter):
    """Adapter for security scanning and vulnerability analysis."""

    def __init__(self):
        super().__init__(
            name="security_scanner",
            adapter_type=AdapterType.DETERMINISTIC,
            description="Perform security analysis and vulnerability scanning",
        )

    def execute(
        self,
        step: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None,
        files: Optional[str] = None,
    ) -> AdapterResult:
        """Execute security scanning."""
        self._log_execution_start(step)

        try:
            with_params = self._extract_with_params(step)
            target_files = with_params.get("target_files", [])
            scan_types = with_params.get("scan_types", ["static_analysis", "secrets", "dependencies"])
            severity_threshold = with_params.get("severity_threshold", "medium")
            include_recommendations = with_params.get("include_recommendations", True)

            if not target_files:
                return AdapterResult(
                    success=False,
                    error="Missing required parameter: target_files"
                )

            scan_results = {
                "scan_timestamp": self._get_timestamp(),
                "target_files": target_files,
                "scan_types": scan_types,
                "severity_threshold": severity_threshold,
                "include_recommendations": include_recommendations,
                "file_results": [],
                "summary": {
                    "total_files": 0,
                    "files_scanned": 0,
                    "total_issues": 0,
                    "critical_issues": 0,
                    "high_issues": 0,
                    "medium_issues": 0,
                    "low_issues": 0,
                    "info_issues": 0
                }
            }

            # Scan each file
            for file_path in target_files:
                file_result = self._scan_file(file_path, scan_types, include_recommendations)
                scan_results["file_results"].append(file_result)

                scan_results["summary"]["total_files"] += 1
                if file_result.get("scanned", False):
                    scan_results["summary"]["files_scanned"] += 1

                # Count issues by severity
                issues = file_result.get("issues", [])
                scan_results["summary"]["total_issues"] += len(issues)

                for issue in issues:
                    severity = issue.get("severity", "info").lower()
                    if severity == "critical":
                        scan_results["summary"]["critical_issues"] += 1
                    elif severity == "high":
                        scan_results["summary"]["high_issues"] += 1
                    elif severity == "medium":
                        scan_results["summary"]["medium_issues"] += 1
                    elif severity == "low":
                        scan_results["summary"]["low_issues"] += 1
                    else:
                        scan_results["summary"]["info_issues"] += 1

            # Determine overall success based on severity threshold
            overall_success = self._evaluate_security_success(scan_results["summary"], severity_threshold)

            # Write scan results
            emit_paths = self._extract_emit_paths(step)
            artifacts = []

            if emit_paths:
                for emit_path in emit_paths:
                    artifact_path = Path(emit_path)
                    artifact_path.parent.mkdir(parents=True, exist_ok=True)

                    with open(artifact_path, 'w', encoding='utf-8') as f:
                        import json
                        json.dump(scan_results, f, indent=2)

                    artifacts.append(str(artifact_path))
                    self.logger.info(f"Security scan results written to: {artifact_path}")

            result = AdapterResult(
                success=overall_success,
                tokens_used=0,  # Deterministic operation
                artifacts=artifacts,
                output=f"Scanned {scan_results['summary']['files_scanned']} files, found {scan_results['summary']['total_issues']} security issues ({scan_results['summary']['critical_issues']} critical, {scan_results['summary']['high_issues']} high)",
                metadata=scan_results
            )

            self._log_execution_complete(result)
            return result

        except Exception as e:
            error_msg = f"Security scanning failed: {str(e)}"
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
        """Check if security scanning tools are available."""
        return True  # Basic security patterns are always available

    def _scan_file(self, file_path: str, scan_types: List[str], include_recommendations: bool) -> Dict[str, Any]:
        """Scan a single file for security issues."""
        file_result = {
            "file_path": file_path,
            "language": None,
            "scanned": False,
            "issues": [],
            "recommendations": [] if include_recommendations else None
        }

        try:
            target_file = Path(file_path)

            if not target_file.exists():
                file_result["issues"].append({
                    "type": "FileNotFound",
                    "severity": "info",
                    "message": f"File not found: {file_path}"
                })
                return file_result

            # Determine language
            language = self._detect_language(target_file)
            file_result["language"] = language
            file_result["scanned"] = True

            # Perform different types of scans
            if "static_analysis" in scan_types:
                self._static_analysis_scan(target_file, file_result, language)

            if "secrets" in scan_types:
                self._secrets_scan(target_file, file_result)

            if "dependencies" in scan_types and language in ["python", "javascript", "typescript"]:
                self._dependency_scan(target_file, file_result, language)

            if "code_patterns" in scan_types:
                self._code_pattern_scan(target_file, file_result, language)

            # Add recommendations if requested
            if include_recommendations and file_result["issues"]:
                self._generate_recommendations(file_result, language)

        except Exception as e:
            file_result["issues"].append({
                "type": "ScanException",
                "severity": "medium",
                "message": f"Security scan exception: {str(e)}"
            })

        return file_result

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
            ".sh": "shell",
            ".bash": "shell",
            ".bat": "batch",
            ".ps1": "powershell",
            ".sql": "sql",
            ".php": "php",
            ".java": "java",
            ".c": "c",
            ".cpp": "cpp",
            ".h": "c",
            ".hpp": "cpp"
        }

        return language_map.get(extension, "unknown")

    def _static_analysis_scan(self, file_path: Path, result: Dict[str, Any], language: str) -> None:
        """Perform static analysis security scanning."""
        if language == "python":
            self._scan_python_security(file_path, result)
        elif language in ["javascript", "typescript"]:
            self._scan_js_security(file_path, result)
        elif language == "shell":
            self._scan_shell_security(file_path, result)
        elif language == "sql":
            self._scan_sql_security(file_path, result)

    def _scan_python_security(self, file_path: Path, result: Dict[str, Any]) -> None:
        """Scan Python code for security issues."""
        try:
            with open(file_path, encoding='utf-8') as f:
                content = f.read()

            # Try to parse AST for more detailed analysis
            try:
                tree = ast.parse(content, filename=str(file_path))
                self._analyze_python_ast(tree, result)
            except SyntaxError:
                pass  # Fall back to text-based analysis

            # Text-based pattern matching
            self._scan_python_patterns(content, result)

        except Exception as e:
            result["issues"].append({
                "type": "PythonScanError",
                "severity": "low",
                "message": f"Failed to scan Python file: {str(e)}"
            })

    def _analyze_python_ast(self, tree: ast.AST, result: Dict[str, Any]) -> None:
        """Analyze Python AST for security issues."""
        dangerous_functions = {
            'eval': 'critical',
            'exec': 'critical',
            'compile': 'high',
            '__import__': 'high',
            'getattr': 'medium',
            'setattr': 'medium',
            'delattr': 'medium',
            'globals': 'medium',
            'locals': 'medium',
            'vars': 'medium'
        }

        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                func_name = node.func.id
                if func_name in dangerous_functions:
                    result["issues"].append({
                        "type": "DangerousFunction",
                        "severity": dangerous_functions[func_name],
                        "message": f"Use of potentially dangerous function: {func_name}",
                        "line": node.lineno,
                        "function": func_name
                    })

            # Check for SQL injection patterns
            elif isinstance(node, ast.Call) and hasattr(node.func, 'attr'):
                if node.func.attr in ['execute', 'query'] and node.args:
                    # Check if SQL query uses string formatting
                    for arg in node.args:
                        if isinstance(arg, (ast.BinOp, ast.JoinedStr, ast.FormattedValue)):
                            result["issues"].append({
                                "type": "SQLInjection",
                                "severity": "high",
                                "message": "Potential SQL injection vulnerability - use parameterized queries",
                                "line": node.lineno
                            })

    def _scan_python_patterns(self, content: str, result: Dict[str, Any]) -> None:
        """Scan Python content for security patterns."""
        patterns = [
            {
                "pattern": r"subprocess\.call\([^)]*shell\s*=\s*True",
                "type": "CommandInjection",
                "severity": "high",
                "message": "Command injection risk with shell=True"
            },
            {
                "pattern": r"os\.system\s*\(",
                "type": "CommandInjection",
                "severity": "high",
                "message": "Command injection risk with os.system"
            },
            {
                "pattern": r"pickle\.loads?\s*\(",
                "type": "DeserializationRisk",
                "severity": "high",
                "message": "Unsafe deserialization with pickle"
            },
            {
                "pattern": r"yaml\.load\s*\(",
                "type": "DeserializationRisk",
                "severity": "medium",
                "message": "Use yaml.safe_load instead of yaml.load"
            },
            {
                "pattern": r"random\.random\s*\(",
                "type": "WeakRandom",
                "severity": "low",
                "message": "Use secrets module for cryptographic randomness"
            }
        ]

        self._apply_regex_patterns(content, patterns, result)

    def _scan_js_security(self, file_path: Path, result: Dict[str, Any]) -> None:
        """Scan JavaScript/TypeScript code for security issues."""
        try:
            with open(file_path, encoding='utf-8') as f:
                content = f.read()

            patterns = [
                {
                    "pattern": r"eval\s*\(",
                    "type": "DangerousFunction",
                    "severity": "critical",
                    "message": "Use of eval() function is dangerous"
                },
                {
                    "pattern": r"innerHTML\s*=",
                    "type": "XSSRisk",
                    "severity": "high",
                    "message": "Direct innerHTML assignment may lead to XSS"
                },
                {
                    "pattern": r"document\.write\s*\(",
                    "type": "XSSRisk",
                    "severity": "high",
                    "message": "document.write can lead to XSS vulnerabilities"
                },
                {
                    "pattern": r"setTimeout\s*\(\s*['\"]",
                    "type": "CodeInjection",
                    "severity": "medium",
                    "message": "Avoid setTimeout with string arguments"
                },
                {
                    "pattern": r"setInterval\s*\(\s*['\"]",
                    "type": "CodeInjection",
                    "severity": "medium",
                    "message": "Avoid setInterval with string arguments"
                }
            ]

            self._apply_regex_patterns(content, patterns, result)

        except Exception as e:
            result["issues"].append({
                "type": "JSScanError",
                "severity": "low",
                "message": f"Failed to scan JS/TS file: {str(e)}"
            })

    def _scan_shell_security(self, file_path: Path, result: Dict[str, Any]) -> None:
        """Scan shell scripts for security issues."""
        try:
            with open(file_path, encoding='utf-8') as f:
                content = f.read()

            patterns = [
                {
                    "pattern": r"\$\([^)]*\$",
                    "type": "CommandInjection",
                    "severity": "high",
                    "message": "Potential command injection in command substitution"
                },
                {
                    "pattern": r"eval\s+",
                    "type": "DangerousFunction",
                    "severity": "critical",
                    "message": "Use of eval in shell scripts is dangerous"
                },
                {
                    "pattern": r"rm\s+-rf\s+/",
                    "type": "DestructiveCommand",
                    "severity": "critical",
                    "message": "Dangerous recursive delete command"
                },
                {
                    "pattern": r">\s*/dev/null\s+2>&1",
                    "type": "ErrorSuppression",
                    "severity": "low",
                    "message": "Error suppression may hide security issues"
                }
            ]

            self._apply_regex_patterns(content, patterns, result)

        except Exception as e:
            result["issues"].append({
                "type": "ShellScanError",
                "severity": "low",
                "message": f"Failed to scan shell file: {str(e)}"
            })

    def _scan_sql_security(self, file_path: Path, result: Dict[str, Any]) -> None:
        """Scan SQL files for security issues."""
        try:
            with open(file_path, encoding='utf-8') as f:
                content = f.read().upper()

            patterns = [
                {
                    "pattern": r"DROP\s+TABLE",
                    "type": "DestructiveSQL",
                    "severity": "high",
                    "message": "DROP TABLE statement found"
                },
                {
                    "pattern": r"DELETE\s+FROM\s+\w+\s*;",
                    "type": "DestructiveSQL",
                    "severity": "high",
                    "message": "DELETE without WHERE clause"
                },
                {
                    "pattern": r"UPDATE\s+\w+\s+SET\s+.*\s*;",
                    "type": "DestructiveSQL",
                    "severity": "medium",
                    "message": "UPDATE without WHERE clause"
                }
            ]

            self._apply_regex_patterns(content, patterns, result)

        except Exception as e:
            result["issues"].append({
                "type": "SQLScanError",
                "severity": "low",
                "message": f"Failed to scan SQL file: {str(e)}"
            })

    def _secrets_scan(self, file_path: Path, result: Dict[str, Any]) -> None:
        """Scan file for potential secrets and credentials."""
        try:
            with open(file_path, encoding='utf-8') as f:
                content = f.read()

            secret_patterns = [
                {
                    "pattern": r"(?i)(password|passwd|pwd)\s*[=:]\s*['\"][^'\"]{3,}['\"]",
                    "type": "HardcodedPassword",
                    "severity": "critical",
                    "message": "Hardcoded password detected"
                },
                {
                    "pattern": r"(?i)(api_key|apikey|secret_key|secretkey)\s*[=:]\s*['\"][^'\"]{10,}['\"]",
                    "type": "HardcodedAPIKey",
                    "severity": "critical",
                    "message": "Hardcoded API key detected"
                },
                {
                    "pattern": r"(?i)(token|auth)\s*[=:]\s*['\"][^'\"]{20,}['\"]",
                    "type": "HardcodedToken",
                    "severity": "high",
                    "message": "Hardcoded token detected"
                },
                {
                    "pattern": r"(?i)(private_key|privatekey)\s*[=:]\s*['\"]-----BEGIN",
                    "type": "HardcodedPrivateKey",
                    "severity": "critical",
                    "message": "Hardcoded private key detected"
                },
                {
                    "pattern": r"(?i)(mysql|postgres|mongodb)://[^:]+:[^@]+@",
                    "type": "DatabaseCredentials",
                    "severity": "high",
                    "message": "Database credentials in connection string"
                }
            ]

            self._apply_regex_patterns(content, secret_patterns, result)

        except Exception as e:
            result["issues"].append({
                "type": "SecretsScanError",
                "severity": "low",
                "message": f"Failed to scan for secrets: {str(e)}"
            })

    def _dependency_scan(self, file_path: Path, result: Dict[str, Any], language: str) -> None:
        """Scan for known vulnerable dependencies."""
        try:
            if language == "python":
                # Check if safety is available for Python vulnerability scanning
                try:
                    subprocess.run(
                        ["safety", "--version"],
                        capture_output=True,
                        text=True,
                        timeout=5
                    )
                    # Run safety check if available
                    # This would require a requirements file, so we'll skip for now
                    result["issues"].append({
                        "type": "DependencyInfo",
                        "severity": "info",
                        "message": "Run 'safety check' to scan for known vulnerable dependencies"
                    })
                except (subprocess.TimeoutExpired, FileNotFoundError):
                    result["issues"].append({
                        "type": "MissingTool",
                        "severity": "info",
                        "message": "Install 'safety' for Python dependency vulnerability scanning: pip install safety"
                    })

            elif language in ["javascript", "typescript"]:
                # Check for npm audit
                try:
                    subprocess.run(
                        ["npm", "audit", "--version"],
                        capture_output=True,
                        text=True,
                        timeout=5
                    )
                    result["issues"].append({
                        "type": "DependencyInfo",
                        "severity": "info",
                        "message": "Run 'npm audit' to scan for known vulnerable dependencies"
                    })
                except (subprocess.TimeoutExpired, FileNotFoundError):
                    result["issues"].append({
                        "type": "MissingTool",
                        "severity": "info",
                        "message": "npm not available for dependency vulnerability scanning"
                    })

        except Exception as e:
            result["issues"].append({
                "type": "DependencyScanError",
                "severity": "low",
                "message": f"Failed to scan dependencies: {str(e)}"
            })

    def _code_pattern_scan(self, file_path: Path, result: Dict[str, Any], language: str) -> None:
        """Scan for insecure coding patterns."""
        try:
            with open(file_path, encoding='utf-8') as f:
                content = f.read()

            # Generic insecure patterns
            patterns = [
                {
                    "pattern": r"(?i)todo.*security",
                    "type": "SecurityTODO",
                    "severity": "low",
                    "message": "Security-related TODO comment found"
                },
                {
                    "pattern": r"(?i)fixme.*security",
                    "type": "SecurityFIXME",
                    "severity": "medium",
                    "message": "Security-related FIXME comment found"
                },
                {
                    "pattern": r"(?i)(hack|workaround|temporary).*security",
                    "type": "SecurityWorkaround",
                    "severity": "medium",
                    "message": "Security workaround or hack identified"
                }
            ]

            self._apply_regex_patterns(content, patterns, result)

        except Exception as e:
            result["issues"].append({
                "type": "PatternScanError",
                "severity": "low",
                "message": f"Failed to scan code patterns: {str(e)}"
            })

    def _apply_regex_patterns(self, content: str, patterns: List[Dict], result: Dict[str, Any]) -> None:
        """Apply regex patterns to content and add issues."""
        lines = content.split('\n')

        for pattern_info in patterns:
            pattern = pattern_info["pattern"]
            matches = re.finditer(pattern, content, re.MULTILINE | re.IGNORECASE)

            for match in matches:
                # Find line number
                line_num = content[:match.start()].count('\n') + 1

                issue = {
                    "type": pattern_info["type"],
                    "severity": pattern_info["severity"],
                    "message": pattern_info["message"],
                    "line": line_num,
                    "match": match.group(0)[:100]  # Truncate long matches
                }

                result["issues"].append(issue)

    def _generate_recommendations(self, result: Dict[str, Any], language: str) -> None:
        """Generate security recommendations based on found issues."""
        recommendations = []

        issue_types = set(issue["type"] for issue in result["issues"])

        if "HardcodedPassword" in issue_types or "HardcodedAPIKey" in issue_types:
            recommendations.append({
                "type": "SecretManagement",
                "priority": "high",
                "recommendation": "Use environment variables or secret management systems instead of hardcoded credentials"
            })

        if "SQLInjection" in issue_types:
            recommendations.append({
                "type": "SQLSecurity",
                "priority": "high",
                "recommendation": "Use parameterized queries or ORM to prevent SQL injection"
            })

        if "XSSRisk" in issue_types:
            recommendations.append({
                "type": "XSSPrevention",
                "priority": "high",
                "recommendation": "Sanitize user input and use safe DOM manipulation methods"
            })

        if "CommandInjection" in issue_types:
            recommendations.append({
                "type": "CommandSecurity",
                "priority": "high",
                "recommendation": "Validate and sanitize input before using in shell commands"
            })

        result["recommendations"] = recommendations

    def _evaluate_security_success(self, summary: Dict[str, Any], threshold: str) -> bool:
        """Evaluate if security scan passes based on threshold."""
        threshold_map = {
            "critical": ["critical"],
            "high": ["critical", "high"],
            "medium": ["critical", "high", "medium"],
            "low": ["critical", "high", "medium", "low"]
        }

        failing_severities = threshold_map.get(threshold.lower(), ["critical", "high"])

        for severity in failing_severities:
            if summary.get(f"{severity}_issues", 0) > 0:
                return False

        return True

    def _get_timestamp(self) -> str:
        """Get current timestamp in ISO format."""
        from datetime import datetime
        return datetime.utcnow().isoformat() + "Z"
