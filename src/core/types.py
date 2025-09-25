"""
Strong typing for the multi-tool CLI orchestration system.

This module defines the core types and contracts for tool execution,
configuration management, and error handling.
"""

import time
from dataclasses import dataclass
from enum import Enum
from typing import Any, Literal, Optional, TypedDict, Union


class ToolCapability(str, Enum):
    """Capabilities that tools can provide"""

    CHAT = "chat"
    CODE_EDIT = "code-edit"
    REPO_AWARE = "repo-aware"
    EXPLAIN = "explain"
    EDITOR_INTEGRATION = "editor-integration"
    STREAMING = "streaming"
    ANALYSIS = "analysis"


class StepType(str, Enum):
    """Types of orchestrator steps"""

    TOOL = "tool"
    LLM = "llm"
    SHELL = "shell"
    PYTHON = "python"
    NOOP = "noop"


class CircuitBreakerState(str, Enum):
    """Circuit breaker states for tool reliability"""

    CLOSED = "closed"  # Normal operation
    OPEN = "open"  # Failing, blocking requests
    HALF_OPEN = "half_open"  # Testing if service recovered


class ToolStep(TypedDict, total=False):
    """Type for orchestrator steps that use tools"""

    type: Literal[StepType.TOOL, StepType.LLM]
    prompt: str
    tool: Optional[str]  # Explicit tool slug
    capabilities: Optional[list[ToolCapability]]
    use_tool: bool
    timeout: int
    stream: bool
    context: Optional[dict[str, Any]]


class OrchestratorContext(TypedDict, total=False):
    """Context passed between orchestrator phases"""

    phase: str
    last_tool_output: Optional[str]
    tool_history: list[dict[str, Any]]
    metadata: dict[str, Any]
    preferred_tool: Optional[str]


class ToolAvailability(TypedDict):
    """Tool availability status with detailed information"""

    available: bool
    reason: Optional[str]
    version: Optional[str]
    health_status: Optional[str]


@dataclass
class ToolExecutionResult:
    """Standardized result from tool execution"""

    success: bool
    output: str
    error: Optional[str] = None
    duration_ms: Optional[int] = None
    tool_slug: Optional[str] = None
    metadata: Optional[dict[str, Any]] = None


@dataclass
class CircuitBreakerConfig:
    """Configuration for circuit breaker behavior"""

    failure_threshold: int = 3
    timeout_seconds: int = 60
    half_open_max_attempts: int = 1


@dataclass
class CircuitBreakerMetrics:
    """Metrics tracked by circuit breaker"""

    failure_count: int = 0
    success_count: int = 0
    last_failure_time: Optional[float] = None
    last_success_time: Optional[float] = None
    state: CircuitBreakerState = CircuitBreakerState.CLOSED

    def record_success(self):
        """Record a successful operation"""
        self.success_count += 1
        self.last_success_time = time.time()
        self.failure_count = 0  # Reset failure count on success
        self.state = CircuitBreakerState.CLOSED

    def record_failure(self):
        """Record a failed operation"""
        self.failure_count += 1
        self.last_failure_time = time.time()

    def should_open(self, config: CircuitBreakerConfig) -> bool:
        """Check if circuit breaker should open due to failures"""
        return self.failure_count >= config.failure_threshold

    def can_attempt_half_open(self, config: CircuitBreakerConfig) -> bool:
        """Check if we can attempt a half-open state"""
        if self.state != CircuitBreakerState.OPEN:
            return False

        if self.last_failure_time is None:
            return True

        time_since_failure = time.time() - self.last_failure_time
        return time_since_failure >= config.timeout_seconds


class ValidationRule(TypedDict):
    """Configuration validation rule"""

    name: str
    description: str
    validator_function: str  # Function name or path
    error_message: str
    warning_only: bool


class ConfigTransaction(TypedDict):
    """Configuration transaction metadata"""

    transaction_id: str
    timestamp: float
    changes: list[dict[str, Any]]
    rollback_data: dict[str, Any]
    validation_results: list[dict[str, Any]]


class ToolMetrics(TypedDict):
    """Metrics for tool performance tracking"""

    total_executions: int
    successful_executions: int
    failed_executions: int
    average_duration_ms: float
    p95_duration_ms: float
    last_execution_time: float
    circuit_breaker_state: CircuitBreakerState


class RegistryEntry(TypedDict):
    """Entry in the tool registry"""

    tool_slug: str
    adapter_class: str
    adapter_path: str
    capabilities: list[ToolCapability]
    active: bool
    priority: int
    metadata: dict[str, Any]


class ToolConfig(TypedDict, total=False):
    """Configuration for a specific tool"""

    enabled: bool
    binary_path: Optional[str]
    arguments: list[str]
    environment: dict[str, str]
    timeout_seconds: int
    retry_attempts: int
    circuit_breaker: CircuitBreakerConfig


class SystemConfig(TypedDict):
    """Overall system configuration"""

    tools: dict[str, ToolConfig]
    registry: list[RegistryEntry]
    default_timeout: int
    max_parallel_executions: int
    log_level: str
    metrics_enabled: bool


# Error types for better error handling
class ToolError(Exception):
    """Base exception for tool-related errors"""

    pass


class ToolUnavailableError(ToolError):
    """Raised when a tool is not available"""

    pass


class ToolExecutionError(ToolError):
    """Raised when tool execution fails"""

    pass


class CircuitBreakerOpenError(ToolError):
    """Raised when circuit breaker is open"""

    pass


class ConfigurationError(Exception):
    """Raised when configuration is invalid"""

    pass


class ValidationError(Exception):
    """Raised when validation fails"""

    pass


# Type aliases for common patterns
ToolSlug = str
CapabilitySet = set[ToolCapability]
ExecutionContext = dict[str, Any]
ConfigPath = str
ValidationResult = dict[str, Union[bool, str, list[str]]]
