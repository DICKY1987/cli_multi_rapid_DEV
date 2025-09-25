# Verification Framework Plugin System (MOD-005)

## Overview

The verification framework extends the existing gate-based quality control system with a plugin architecture that allows for:

- **Pluggable verification logic**: Custom verification plugins for different tools and frameworks
- **Unified interface**: Consistent API for all verification plugins
- **Built-in plugins**: Ready-to-use plugins for common tools (pytest, ruff, semgrep, schema validation)
- **Health monitoring**: Plugin dependency checking and status monitoring
- **Backward compatibility**: Existing gate-based system continues to work alongside plugins

## Architecture

### Core Components

#### Plugin System (`src/cli_multi_rapid/plugins/`)
- **BasePlugin**: Abstract base class defining the plugin interface
- **PluginManager**: Discovers, loads, and manages plugin lifecycle
- **PluginResult**: Standardized result structure for plugin execution

#### Built-in Plugins (`src/cli_multi_rapid/plugins/builtin/`)
- **PytestPlugin**: Executes pytest tests with coverage reporting
- **RuffSemgrepPlugin**: Code quality and security analysis
- **SchemaValidatePlugin**: JSON Schema validation for artifacts

#### Enhanced Verifier (`src/cli_multi_rapid/verifier.py`)
- Extended existing `Verifier` class with plugin support
- `VerifierAdapter` enhanced to handle plugin-based verification
- Backward compatibility with existing gate system

## Plugin Interface

### BasePlugin Class

```python
class BasePlugin(abc.ABC):
    def get_capabilities(self) -> Dict[str, Any]:
        """Return plugin capabilities and metadata."""

    def validate_config(self, config: Dict[str, Any]) -> bool:
        """Validate plugin configuration."""

    def execute(
        self, config: Dict[str, Any],
        artifacts_dir: Path,
        context: Dict[str, Any]
    ) -> PluginResult:
        """Execute the plugin with given configuration."""

    def get_required_tools(self) -> List[str]:
        """Return list of required external tools/dependencies."""

    def check_dependencies(self) -> Dict[str, bool]:
        """Check if all dependencies are available."""
```

### PluginResult Structure

```python
@dataclass
class PluginResult:
    plugin_name: str
    passed: bool
    message: str
    details: Dict[str, Any] = None
    artifacts_created: List[str] = None
    execution_time_ms: float = 0.0
```

## Built-in Plugins

### 1. Pytest Plugin

Executes pytest tests with coverage reporting and structured output.

**Capabilities:**
- Test execution with configurable paths
- Coverage threshold enforcement
- JSON output for test results and coverage
- Configurable pytest arguments

**Configuration:**
```yaml
plugin: pytest
config:
  test_paths: ["tests/"]
  coverage_threshold: 80
  pytest_args: ["--tb=short", "-v"]
```

**Outputs:**
- `test_results.json`: Detailed test execution results
- `coverage.json`: Code coverage data

### 2. Ruff + Semgrep Plugin

Code quality and security analysis using ruff linter and semgrep static analysis.

**Capabilities:**
- Ruff linting with configurable rules
- Semgrep security analysis
- Combined violation reporting
- Configurable violation thresholds

**Configuration:**
```yaml
plugin: ruff_semgrep
config:
  paths: ["src/", "tests/"]
  max_violations: 5
  ruff_rules: ["E", "W", "F"]
  semgrep_rules: ["auto"]
```

**Outputs:**
- `ruff_results.json`: Ruff linting results
- `semgrep_results.json`: Semgrep analysis results
- `lint_summary.json`: Combined analysis summary

### 3. Schema Validation Plugin

Validates JSON artifacts against JSON Schema definitions.

**Capabilities:**
- JSON Schema validation for workflow artifacts
- Filename-based schema mapping heuristics
- Custom schema mappings
- Comprehensive validation reporting

**Configuration:**
```yaml
plugin: schema_validate
config:
  artifacts: ["test_results.json", "coverage.json"]
  schema_dir: ".ai/schemas"
  schema_mapping:
    "custom_artifact.json": "custom.schema.json"
```

**Outputs:**
- `schema_validation.json`: Validation results for all artifacts

## Usage in Workflows

### Plugin-Only Verification

```yaml
steps:
  - id: "1.001"
    name: "Run Quality Checks"
    actor: verifier
    with:
      verification:
        plugins:
          - plugin: pytest
            config:
              test_paths: ["tests/"]
              coverage_threshold: 80
          - plugin: ruff_semgrep
            config:
              paths: ["src/"]
              max_violations: 0
```

### Combined Traditional + Plugin Verification

```yaml
steps:
  - id: "1.001"
    name: "Comprehensive Verification"
    actor: verifier
    with:
      verification:
        # Traditional gates
        tests: true
        schema: true
        diff_limits:
          max_loc: 500
        # Plugin gates
        plugins:
          - plugin: pytest
            config:
              coverage_threshold: 85
          - plugin: schema_validate
            config:
              artifacts: ["test_results.json"]
```

## Plugin Development

### Creating Custom Plugins

1. **Extend BasePlugin**:
```python
from cli_multi_rapid.plugins.base_plugin import BasePlugin, PluginResult

class MyCustomPlugin(BasePlugin):
    def __init__(self):
        super().__init__("my_plugin", "1.0.0")

    def get_capabilities(self):
        return {
            "description": "My custom verification plugin",
            "requires_tools": ["mytool"],
            "outputs": ["my_results.json"]
        }

    def validate_config(self, config):
        # Validate configuration
        return True

    def execute(self, config, artifacts_dir, context):
        # Plugin logic here
        return PluginResult(
            plugin_name=self.name,
            passed=True,
            message="Custom check passed"
        )
```

2. **Register Plugin**:
Add to `PluginManager._discover_plugins()` or place in `builtin/` directory.

### Plugin Best Practices

1. **Configuration Validation**: Always validate configuration in `validate_config()`
2. **Dependency Checking**: Use `get_required_tools()` and `check_dependencies()`
3. **Error Handling**: Wrap execution in try/catch and return meaningful error messages
4. **Artifact Creation**: Always populate `artifacts_created` in PluginResult
5. **Performance**: Use timing to track execution performance

## Integration with Existing System

### Backward Compatibility

The plugin system is fully backward compatible:
- Existing workflows continue to work unchanged
- Traditional gates (`tests_pass`, `schema_valid`, etc.) remain functional
- Plugin system is opt-in via the `plugins` section in verification plans

### Enhanced VerifierAdapter

The `VerifierAdapter` class now supports both traditional gates and plugin-based verification:

```python
verification_plan = {
    "tests": True,  # Traditional gate
    "plugins": [    # Plugin gates
        {
            "plugin": "pytest",
            "config": {"coverage_threshold": 80}
        }
    ]
}
```

## Monitoring and Health Checks

### Plugin Health Monitoring

```python
verifier = Verifier()
health = verifier.get_plugin_health()
# Returns:
# {
#   "plugin_manager_enabled": True,
#   "available_plugins": ["pytest", "ruff_semgrep", "schema_validate"],
#   "plugin_health": {
#     "pytest": {
#       "available": True,
#       "dependencies_ok": True,
#       "dependencies": {"pytest": True},
#       "capabilities": {...}
#     }
#   }
# }
```

### Dependency Checking

```python
plugin_manager = PluginManager()
deps = plugin_manager.check_plugin_dependencies("pytest")
# Returns: {"pytest": True}
```

## Error Handling and Diagnostics

### Plugin Execution Errors

Plugins handle errors gracefully:
- Configuration validation errors
- Missing tool dependencies
- Runtime execution errors
- Timeout handling (via execution timing)

### Diagnostic Information

Each `PluginResult` includes:
- Execution timing (`execution_time_ms`)
- Detailed error information (`details`)
- Created artifacts list (`artifacts_created`)
- Success/failure status with descriptive messages

## Configuration Examples

### Comprehensive Example

```yaml
name: "Full Plugin Verification"
steps:
  - id: "verify"
    actor: verifier
    with:
      verification:
        # Traditional gates
        tests: true
        schema: true
        diff_limits:
          max_loc: 1000

        # Plugin-based verification
        plugins:
          # Test execution with coverage
          - plugin: pytest
            config:
              test_paths: ["tests/unit/", "tests/integration/"]
              coverage_threshold: 85
              pytest_args: ["--tb=short", "--durations=10"]

          # Code quality and security
          - plugin: ruff_semgrep
            config:
              paths: ["src/", "tests/"]
              max_violations: 0
              ruff_rules: ["E", "W", "F", "B", "S"]
              semgrep_rules: ["python.security", "python.best-practice"]

          # Schema validation
          - plugin: schema_validate
            config:
              artifacts: ["test_results.json", "coverage.json", "lint_summary.json"]
              schema_dir: ".ai/schemas"
              schema_mapping:
                "custom_report.json": "custom_report.schema.json"

    gates:
      - type: "tests_pass"
      - type: "schema_valid"
      - type: "diff_limits"
        max_lines: 1000
```

## Future Extensions

The plugin framework is designed for extensibility:

- **Custom Tool Integration**: Easy integration of new linting tools, test frameworks
- **Cloud Service Plugins**: Integration with external quality services
- **Notification Plugins**: Send results to Slack, email, etc.
- **Reporting Plugins**: Generate custom reports (HTML, PDF, etc.)
- **Security Scanning**: Integration with vulnerability scanners
- **Performance Testing**: Load testing and benchmark plugins

## API Reference

### PluginManager Methods

- `get_plugin(name: str) -> BasePlugin`: Get plugin instance
- `list_plugins() -> List[str]`: List available plugins
- `execute_plugin(name, config, artifacts_dir, context) -> PluginResult`: Execute plugin
- `get_plugin_health() -> Dict[str, Any]`: Get health status of all plugins

### Verifier Enhancements

- `check_plugin_gates(configs, artifacts_dir, context) -> List[PluginResult]`: Execute plugin gates
- `get_plugin_health() -> Dict[str, Any]`: Get plugin health status

This plugin framework provides a robust, extensible foundation for verification and quality gates in the CLI Orchestrator, maintaining backward compatibility while enabling powerful new capabilities through MOD-005.
