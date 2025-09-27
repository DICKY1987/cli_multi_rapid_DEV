#!/usr/bin/env python3
"""
Import Resolver Adapter

Resolves and validates import statements, identifies missing dependencies,
and suggests fixes for import-related issues in the Codex pipeline.
"""

import ast
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from .base_adapter import AdapterResult, AdapterType, BaseAdapter


class ImportResolverAdapter(BaseAdapter):
    """Adapter for resolving and validating import statements."""

    def __init__(self):
        super().__init__(
            name="import_resolver",
            adapter_type=AdapterType.DETERMINISTIC,
            description="Resolve and validate import statements across multiple languages",
        )

    def execute(
        self,
        step: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None,
        files: Optional[str] = None,
    ) -> AdapterResult:
        """Execute import resolution and validation."""
        self._log_execution_start(step)

        try:
            with_params = self._extract_with_params(step)
            target_files = with_params.get("target_files", [])
            languages = with_params.get("languages", ["python"])
            check_availability = with_params.get("check_availability", True)
            suggest_fixes = with_params.get("suggest_fixes", True)

            if not target_files:
                return AdapterResult(
                    success=False,
                    error="Missing required parameter: target_files"
                )

            resolution_results = {
                "resolution_timestamp": self._get_timestamp(),
                "target_files": target_files,
                "languages": languages,
                "check_availability": check_availability,
                "suggest_fixes": suggest_fixes,
                "file_analyses": [],
                "summary": {
                    "total_files": 0,
                    "files_with_imports": 0,
                    "total_imports": 0,
                    "resolved_imports": 0,
                    "unresolved_imports": 0,
                    "missing_dependencies": []
                }
            }

            # Analyze each file
            for file_path in target_files:
                file_analysis = self._analyze_file_imports(file_path, languages, check_availability, suggest_fixes)
                resolution_results["file_analyses"].append(file_analysis)

                resolution_results["summary"]["total_files"] += 1
                if file_analysis.get("imports"):
                    resolution_results["summary"]["files_with_imports"] += 1

                imports = file_analysis.get("imports", [])
                resolution_results["summary"]["total_imports"] += len(imports)

                for imp in imports:
                    if imp.get("resolved", False):
                        resolution_results["summary"]["resolved_imports"] += 1
                    else:
                        resolution_results["summary"]["unresolved_imports"] += 1

                # Collect missing dependencies
                missing_deps = file_analysis.get("missing_dependencies", [])
                for dep in missing_deps:
                    if dep not in resolution_results["summary"]["missing_dependencies"]:
                        resolution_results["summary"]["missing_dependencies"].append(dep)

            # Determine overall success (all imports resolved)
            overall_success = resolution_results["summary"]["unresolved_imports"] == 0

            # Write resolution results
            emit_paths = self._extract_emit_paths(step)
            artifacts = []

            if emit_paths:
                for emit_path in emit_paths:
                    artifact_path = Path(emit_path)
                    artifact_path.parent.mkdir(parents=True, exist_ok=True)

                    with open(artifact_path, 'w', encoding='utf-8') as f:
                        import json
                        json.dump(resolution_results, f, indent=2)

                    artifacts.append(str(artifact_path))
                    self.logger.info(f"Import resolution results written to: {artifact_path}")

            result = AdapterResult(
                success=overall_success,
                tokens_used=0,  # Deterministic operation
                artifacts=artifacts,
                output=f"Analyzed {resolution_results['summary']['total_imports']} imports across {resolution_results['summary']['total_files']} files, {resolution_results['summary']['resolved_imports']} resolved, {resolution_results['summary']['unresolved_imports']} unresolved",
                metadata=resolution_results
            )

            self._log_execution_complete(result)
            return result

        except Exception as e:
            error_msg = f"Import resolution failed: {str(e)}"
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
        return True  # Basic import analysis is always available

    def _analyze_file_imports(self, file_path: str, languages: List[str], check_availability: bool, suggest_fixes: bool) -> Dict[str, Any]:
        """Analyze imports for a single file."""
        file_analysis = {
            "file_path": file_path,
            "language": None,
            "imports": [],
            "missing_dependencies": [],
            "suggestions": [],
            "errors": []
        }

        try:
            target_file = Path(file_path)

            if not target_file.exists():
                file_analysis["errors"].append(f"File not found: {file_path}")
                return file_analysis

            # Determine language
            language = self._detect_language(target_file)
            file_analysis["language"] = language

            # Analyze based on language
            if language == "python" and ("python" in languages or "auto" in languages):
                self._analyze_python_imports(target_file, file_analysis, check_availability, suggest_fixes)
            elif language in ["javascript", "typescript"] and (language in languages or "auto" in languages):
                self._analyze_js_ts_imports(target_file, file_analysis, check_availability, suggest_fixes)
            else:
                file_analysis["errors"].append(f"Unsupported language for import analysis: {language}")

        except Exception as e:
            file_analysis["errors"].append(f"Analysis exception: {str(e)}")

        return file_analysis

    def _detect_language(self, file_path: Path) -> str:
        """Detect programming language from file extension."""
        extension = file_path.suffix.lower()

        language_map = {
            ".py": "python",
            ".js": "javascript",
            ".jsx": "javascript",
            ".ts": "typescript",
            ".tsx": "typescript"
        }

        return language_map.get(extension, "unknown")

    def _analyze_python_imports(self, file_path: Path, analysis: Dict[str, Any], check_availability: bool, suggest_fixes: bool) -> None:
        """Analyze Python imports using AST."""
        try:
            with open(file_path, encoding='utf-8') as f:
                source_code = f.read()

            tree = ast.parse(source_code, filename=str(file_path))

            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        import_info = {
                            "type": "import",
                            "module": alias.name,
                            "alias": alias.asname,
                            "line": node.lineno,
                            "resolved": False,
                            "available": None
                        }

                        if check_availability:
                            import_info["available"] = self._check_python_module_availability(alias.name)
                            import_info["resolved"] = import_info["available"]

                        analysis["imports"].append(import_info)

                elif isinstance(node, ast.ImportFrom):
                    module = node.module or ""
                    for alias in node.names:
                        import_info = {
                            "type": "from_import",
                            "module": module,
                            "name": alias.name,
                            "alias": alias.asname,
                            "line": node.lineno,
                            "level": node.level,
                            "resolved": False,
                            "available": None
                        }

                        if check_availability:
                            if node.level > 0:  # Relative import
                                import_info["available"] = self._check_relative_import(file_path, module, node.level)
                            else:  # Absolute import
                                import_info["available"] = self._check_python_module_availability(module)
                            import_info["resolved"] = import_info["available"]

                        analysis["imports"].append(import_info)

            # Collect missing dependencies and suggestions
            if check_availability:
                missing_modules = set()
                for imp in analysis["imports"]:
                    if not imp.get("available", True):
                        if imp["type"] == "import":
                            missing_modules.add(imp["module"])
                        elif imp["type"] == "from_import" and imp["module"]:
                            missing_modules.add(imp["module"])

                analysis["missing_dependencies"] = list(missing_modules)

                if suggest_fixes and missing_modules:
                    self._suggest_python_fixes(analysis, missing_modules)

        except SyntaxError as e:
            analysis["errors"].append(f"Python syntax error: {e.msg} at line {e.lineno}")
        except Exception as e:
            analysis["errors"].append(f"Python import analysis error: {str(e)}")

    def _check_python_module_availability(self, module_name: str) -> bool:
        """Check if a Python module is available."""
        try:
            # Try to import the module
            __import__(module_name)
            return True
        except ImportError:
            # Check if it's a standard library module
            return self._is_stdlib_module(module_name)

    def _is_stdlib_module(self, module_name: str) -> bool:
        """Check if a module is part of Python standard library."""
        # This is a simplified check - in production, you'd want a more comprehensive list
        stdlib_modules = {
            'os', 'sys', 'json', 're', 'datetime', 'pathlib', 'subprocess',
            'collections', 'itertools', 'functools', 'typing', 'asyncio',
            'urllib', 'http', 'email', 'xml', 'html', 'csv', 'sqlite3',
            'hashlib', 'hmac', 'secrets', 'uuid', 'random', 'math', 'statistics',
            'decimal', 'fractions', 'cmath', 'time', 'calendar', 'locale',
            'gettext', 'logging', 'warnings', 'traceback', 'pdb', 'profile',
            'timeit', 'doctest', 'unittest', 'test', 'threading', 'multiprocessing',
            'concurrent', 'queue', 'socket', 'ssl', 'select', 'selectors',
            'signal', 'mmap', 'ctypes', 'struct', 'codecs', 'io', 'stringprep',
            'textwrap', 'unicodedata', 'difflib', 'readline', 'rlcompleter'
        }

        base_module = module_name.split('.')[0]
        return base_module in stdlib_modules

    def _check_relative_import(self, file_path: Path, module: str, level: int) -> bool:
        """Check if a relative import can be resolved."""
        try:
            current_dir = file_path.parent

            # Go up 'level' directories
            target_dir = current_dir
            for _ in range(level - 1):
                target_dir = target_dir.parent

            if module:
                # Check for module.py or module/__init__.py
                module_file = target_dir / f"{module}.py"
                module_dir = target_dir / module / "__init__.py"
                return module_file.exists() or module_dir.exists()
            else:
                # Just checking if the parent package exists
                return (target_dir / "__init__.py").exists()

        except Exception:
            return False

    def _analyze_js_ts_imports(self, file_path: Path, analysis: Dict[str, Any], check_availability: bool, suggest_fixes: bool) -> None:
        """Analyze JavaScript/TypeScript imports (basic regex-based approach)."""
        try:
            with open(file_path, encoding='utf-8') as f:
                content = f.read()

            import re

            # Match ES6 imports
            import_patterns = [
                r"import\s+(?:{[^}]+}|\w+|\*\s+as\s+\w+)\s+from\s+['\"]([^'\"]+)['\"]",
                r"import\s+['\"]([^'\"]+)['\"]",
                r"const\s+(?:{[^}]+}|\w+)\s*=\s*require\s*\(\s*['\"]([^'\"]+)['\"]\s*\)"
            ]

            line_number = 1
            for line in content.split('\n'):
                for pattern in import_patterns:
                    matches = re.finditer(pattern, line)
                    for match in matches:
                        module_path = match.group(1)

                        import_info = {
                            "type": "import",
                            "module": module_path,
                            "line": line_number,
                            "resolved": False,
                            "available": None
                        }

                        if check_availability:
                            import_info["available"] = self._check_js_module_availability(file_path, module_path)
                            import_info["resolved"] = import_info["available"]

                        analysis["imports"].append(import_info)

                line_number += 1

            # Collect missing dependencies
            if check_availability:
                missing_modules = set()
                for imp in analysis["imports"]:
                    if not imp.get("available", True):
                        missing_modules.add(imp["module"])

                analysis["missing_dependencies"] = list(missing_modules)

                if suggest_fixes and missing_modules:
                    self._suggest_js_fixes(analysis, missing_modules)

        except Exception as e:
            analysis["errors"].append(f"JS/TS import analysis error: {str(e)}")

    def _check_js_module_availability(self, file_path: Path, module_path: str) -> bool:
        """Check if a JavaScript/TypeScript module is available."""
        try:
            # Relative imports
            if module_path.startswith('.'):
                # Resolve relative path
                current_dir = file_path.parent
                resolved_path = (current_dir / module_path).resolve()

                # Check for various file extensions
                for ext in ['.js', '.ts', '.jsx', '.tsx', '.json']:
                    if (resolved_path.parent / (resolved_path.name + ext)).exists():
                        return True

                # Check for index files
                for ext in ['.js', '.ts', '.jsx', '.tsx']:
                    if (resolved_path / ('index' + ext)).exists():
                        return True

                return False

            # Check node_modules
            node_modules = file_path.parent
            while node_modules.parent != node_modules:
                node_modules_dir = node_modules / 'node_modules' / module_path
                if node_modules_dir.exists():
                    return True
                node_modules = node_modules.parent

            return False

        except Exception:
            return False

    def _suggest_python_fixes(self, analysis: Dict[str, Any], missing_modules: Set[str]) -> None:
        """Suggest fixes for missing Python modules."""
        suggestions = []

        for module in missing_modules:
            # Common package mappings
            package_mappings = {
                'cv2': 'opencv-python',
                'PIL': 'Pillow',
                'sklearn': 'scikit-learn',
                'yaml': 'PyYAML',
                'bs4': 'beautifulsoup4',
                'requests': 'requests',
                'numpy': 'numpy',
                'pandas': 'pandas',
                'matplotlib': 'matplotlib',
                'seaborn': 'seaborn',
                'flask': 'Flask',
                'django': 'Django'
            }

            package_name = package_mappings.get(module, module)
            suggestions.append({
                "type": "install_package",
                "module": module,
                "package": package_name,
                "command": f"pip install {package_name}"
            })

        analysis["suggestions"] = suggestions

    def _suggest_js_fixes(self, analysis: Dict[str, Any], missing_modules: Set[str]) -> None:
        """Suggest fixes for missing JavaScript/TypeScript modules."""
        suggestions = []

        for module in missing_modules:
            if not module.startswith('.'):  # Only suggest for npm packages
                suggestions.append({
                    "type": "install_package",
                    "module": module,
                    "package": module,
                    "command": f"npm install {module}"
                })

        analysis["suggestions"] = suggestions

    def _get_timestamp(self) -> str:
        """Get current timestamp in ISO format."""
        from datetime import datetime
        return datetime.utcnow().isoformat() + "Z"
