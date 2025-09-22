"""
Protocol definitions for the multi-tool CLI system.

This module defines the contracts that tools must implement to be compatible
with the orchestration system.
"""

from contextlib import (
    AbstractAsyncContextManager,
    AbstractContextManager,
    contextmanager,
)
from typing import Optional, Protocol, runtime_checkable

from .types import (
    CapabilitySet,
    ExecutionContext,
    ToolAvailability,
    ToolCapability,
    ToolExecutionResult,
)


@runtime_checkable
class BaseTool(Protocol):
    """
    Enhanced tool contract with comprehensive error handling and lifecycle management.

    All tools must implement this protocol to be compatible with the orchestration system.
    """

    name: str
    slug: str
    capabilities: CapabilitySet

    def available(self) -> ToolAvailability:
        """
        Check if tool is available with detailed reason.

        Returns:
            ToolAvailability dict with status, reason, version, and health info
        """
        ...

    def version(self) -> Optional[str]:
        """Return version if discoverable."""
        ...

    @contextmanager
    def session(self) -> AbstractContextManager[None]:
        """
        Context manager for tool lifecycle management.

        This should handle any setup/teardown required for tool execution,
        such as starting background processes, acquiring locks, etc.
        """
        ...

    def execute(
        self,
        prompt: str,
        timeout: int = 120,
        stream: bool = False,
        context: Optional[ExecutionContext] = None,
        **kwargs,
    ) -> ToolExecutionResult:
        """
        Execute tool with comprehensive result.

        Args:
            prompt: The input/command for the tool
            timeout: Maximum execution time in seconds
            stream: Whether to support streaming output
            context: Additional context for execution
            **kwargs: Tool-specific arguments

        Returns:
            ToolExecutionResult with success status, output, and metadata
        """
        ...

    def health_check(self) -> bool:
        """
        Quick health verification.

        Returns:
            True if tool is healthy and ready for execution
        """
        ...


@runtime_checkable
class StreamingTool(Protocol):
    """
    Protocol for tools that support streaming output.

    Tools implementing this protocol can provide real-time output
    during long-running operations.
    """

    async def execute_stream(
        self,
        prompt: str,
        timeout: int = 120,
        context: Optional[ExecutionContext] = None,
        **kwargs,
    ) -> AbstractAsyncContextManager[str]:
        """
        Execute tool with streaming output.

        Args:
            prompt: The input/command for the tool
            timeout: Maximum execution time in seconds
            context: Additional context for execution
            **kwargs: Tool-specific arguments

        Yields:
            Incremental output chunks as they become available
        """
        ...


@runtime_checkable
class ConfigurableTool(Protocol):
    """
    Protocol for tools that support dynamic configuration.

    Tools implementing this protocol can be configured at runtime
    without requiring restart.
    """

    def get_config(self) -> dict:
        """Get current tool configuration."""
        ...

    def update_config(self, config: dict) -> bool:
        """
        Update tool configuration.

        Args:
            config: New configuration values

        Returns:
            True if configuration was successfully updated
        """
        ...

    def validate_config(self, config: dict) -> bool:
        """
        Validate configuration without applying it.

        Args:
            config: Configuration to validate

        Returns:
            True if configuration is valid
        """
        ...


@runtime_checkable
class AnalyticsTool(Protocol):
    """
    Protocol for tools that provide analytics and metrics.

    Tools implementing this protocol can provide insights about
    their usage patterns and performance.
    """

    def get_metrics(self) -> dict:
        """Get tool usage metrics."""
        ...

    def reset_metrics(self) -> None:
        """Reset tool metrics to initial state."""
        ...


@runtime_checkable
class ToolAdapter(Protocol):
    """
    Protocol for tool adapters that wrap external tools.

    Adapters translate between the standard tool interface and
    tool-specific command formats.
    """

    def detect_binary(self) -> Optional[str]:
        """
        Detect the path to the tool binary.

        Returns:
            Path to binary if found, None otherwise
        """
        ...

    def prepare_command(self, prompt: str, **kwargs) -> list[str]:
        """
        Prepare command line arguments for tool execution.

        Args:
            prompt: User input to convert to tool arguments
            **kwargs: Additional parameters

        Returns:
            List of command line arguments
        """
        ...

    def parse_output(
        self, stdout: str, stderr: str, returncode: int
    ) -> ToolExecutionResult:
        """
        Parse tool output into standard result format.

        Args:
            stdout: Standard output from tool
            stderr: Standard error from tool
            returncode: Exit code from tool

        Returns:
            Parsed ToolExecutionResult
        """
        ...


@runtime_checkable
class ToolRegistry(Protocol):
    """
    Protocol for tool registry implementations.

    The registry manages available tools and handles tool selection
    and activation.
    """

    def register_tool(self, slug: str, tool: BaseTool, priority: int = 0) -> bool:
        """Register a tool in the registry."""
        ...

    def unregister_tool(self, slug: str) -> bool:
        """Remove a tool from the registry."""
        ...

    def get_tool(self, slug: str) -> Optional[BaseTool]:
        """Get a specific tool by slug."""
        ...

    def find_tools_by_capability(self, capability: ToolCapability) -> list[BaseTool]:
        """Find all tools that provide a specific capability."""
        ...

    def get_active_tool(self) -> Optional[BaseTool]:
        """Get the currently active tool."""
        ...

    def activate_tool(self, slug: str) -> bool:
        """Activate a specific tool."""
        ...


@runtime_checkable
class ConfigurationManager(Protocol):
    """
    Protocol for configuration management implementations.

    Handles loading, saving, and validating system configuration.
    """

    def load_config(self, path: str) -> dict:
        """Load configuration from file."""
        ...

    def save_config(self, config: dict, path: str) -> bool:
        """Save configuration to file."""
        ...

    def validate_config(self, config: dict) -> bool:
        """Validate configuration against schema."""
        ...

    def merge_configs(self, base: dict, override: dict) -> dict:
        """Merge two configuration dictionaries."""
        ...


@runtime_checkable
class ExecutionOrchestrator(Protocol):
    """
    Protocol for execution orchestrator implementations.

    Coordinates execution of multiple tools and manages workflow.
    """

    def execute_step(
        self, step: dict, context: Optional[dict] = None
    ) -> tuple[bool, Optional[str]]:
        """Execute a single workflow step."""
        ...

    def execute_workflow(
        self, steps: list[dict], context: Optional[dict] = None
    ) -> bool:
        """Execute a complete workflow."""
        ...

    def get_execution_history(self) -> list[dict]:
        """Get history of executed steps."""
        ...


@runtime_checkable
class MetricsCollector(Protocol):
    """
    Protocol for metrics collection implementations.

    Handles collection, aggregation, and reporting of system metrics.
    """

    def record_execution(self, tool_slug: str, duration_ms: int, success: bool) -> None:
        """Record a tool execution for metrics."""
        ...

    def get_tool_metrics(self, tool_slug: str) -> dict:
        """Get metrics for a specific tool."""
        ...

    def get_system_metrics(self) -> dict:
        """Get overall system metrics."""
        ...

    def export_metrics(self, format: str = "json") -> str:
        """Export metrics in specified format."""
        ...
