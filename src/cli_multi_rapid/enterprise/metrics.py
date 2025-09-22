"""
Metrics collection for CLI Orchestrator services.

Provides Prometheus-compatible metrics collection including:
- Request counters and histograms
- Custom business metrics
- Performance monitoring
- Resource utilization tracking
"""

import logging
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from threading import Lock
from typing import Any, Optional, Union

logger = logging.getLogger(__name__)


@dataclass
class MetricSample:
    """A single metric sample."""

    value: Union[int, float]
    timestamp: float = field(default_factory=time.time)
    labels: dict[str, str] = field(default_factory=dict)


class MetricsCollector:
    """Collects and stores metrics for CLI Orchestrator services."""

    def __init__(self, service_name: str):
        self.service_name = service_name
        self._lock = Lock()

        # Metric storage
        self._counters: dict[str, float] = defaultdict(float)
        self._gauges: dict[str, float] = {}
        self._histograms: dict[str, list[float]] = defaultdict(list)
        self._summaries: dict[str, deque] = defaultdict(lambda: deque(maxlen=1000))

        # Labels for metrics
        self._counter_labels: dict[str, dict[str, str]] = {}
        self._gauge_labels: dict[str, dict[str, str]] = {}

        # Initialize default metrics
        self._init_default_metrics()

    def _init_default_metrics(self) -> None:
        """Initialize default metrics for CLI Orchestrator."""
        # Request metrics
        self.counter("requests_total", "Total number of requests processed")
        self.counter("requests_failed", "Total number of failed requests")

        # Workflow metrics
        self.counter("workflows_executed", "Total number of workflows executed")
        self.counter(
            "workflow_steps_completed", "Total number of workflow steps completed"
        )
        self.counter("workflow_steps_failed", "Total number of workflow steps failed")

        # Token usage metrics
        self.counter("tokens_used_total", "Total number of tokens consumed")
        self.gauge("tokens_remaining", "Number of tokens remaining in budget")

        # Performance metrics
        self.histogram("request_duration_seconds", "Request duration in seconds")
        self.histogram(
            "workflow_duration_seconds", "Workflow execution duration in seconds"
        )
        self.histogram("step_duration_seconds", "Individual step duration in seconds")

    def counter(
        self, name: str, description: str = "", labels: Optional[dict[str, str]] = None
    ) -> None:
        """Create or increment a counter metric."""
        with self._lock:
            metric_key = self._make_metric_key(name, labels)
            self._counters[metric_key] += 1
            if labels:
                self._counter_labels[metric_key] = labels or {}

    def inc_counter(
        self, name: str, value: float = 1.0, labels: Optional[dict[str, str]] = None
    ) -> None:
        """Increment a counter by a specific value."""
        with self._lock:
            metric_key = self._make_metric_key(name, labels)
            self._counters[metric_key] += value
            if labels:
                self._counter_labels[metric_key] = labels or {}

    def gauge(
        self,
        name: str,
        value: Optional[float] = None,
        labels: Optional[dict[str, str]] = None,
    ) -> float:
        """Set or get a gauge metric value."""
        metric_key = self._make_metric_key(name, labels)

        if value is not None:
            with self._lock:
                self._gauges[metric_key] = value
                if labels:
                    self._gauge_labels[metric_key] = labels or {}
            return value
        else:
            return self._gauges.get(metric_key, 0.0)

    def histogram(
        self,
        name: str,
        value: Optional[float] = None,
        labels: Optional[dict[str, str]] = None,
    ) -> None:
        """Record a value in a histogram."""
        if value is not None:
            metric_key = self._make_metric_key(name, labels)
            with self._lock:
                self._histograms[metric_key].append(value)
                # Keep only last 1000 samples to prevent memory issues
                if len(self._histograms[metric_key]) > 1000:
                    self._histograms[metric_key] = self._histograms[metric_key][-1000:]

    def summary(
        self, name: str, value: float, labels: Optional[dict[str, str]] = None
    ) -> None:
        """Record a value in a summary."""
        metric_key = self._make_metric_key(name, labels)
        with self._lock:
            self._summaries[metric_key].append(value)

    def time_function(self, metric_name: str, labels: Optional[dict[str, str]] = None):
        """Decorator to time function execution."""

        def decorator(func):
            def wrapper(*args, **kwargs):
                start_time = time.time()
                try:
                    result = func(*args, **kwargs)
                    self.histogram(metric_name, time.time() - start_time, labels)
                    return result
                except Exception:
                    self.histogram(
                        metric_name,
                        time.time() - start_time,
                        {**(labels or {}), "status": "error"},
                    )
                    raise

            return wrapper

        return decorator

    def workflow_metrics(
        self,
        workflow_name: str,
        success: bool,
        duration: float,
        tokens_used: int,
        steps_completed: int,
    ) -> None:
        """Record workflow execution metrics."""
        labels = {
            "workflow": workflow_name,
            "status": "success" if success else "failed",
        }

        self.inc_counter("workflows_executed", 1, labels)
        self.inc_counter("tokens_used_total", tokens_used)
        self.inc_counter(
            "workflow_steps_completed", steps_completed, {"workflow": workflow_name}
        )
        self.histogram("workflow_duration_seconds", duration, labels)

        if not success:
            self.inc_counter("requests_failed", 1, {"type": "workflow"})

    def step_metrics(
        self,
        step_name: str,
        actor: str,
        success: bool,
        duration: float,
        tokens_used: int,
    ) -> None:
        """Record step execution metrics."""
        labels = {
            "step": step_name,
            "actor": actor,
            "status": "success" if success else "failed",
        }

        self.inc_counter(
            "workflow_steps_completed" if success else "workflow_steps_failed",
            1,
            labels,
        )
        self.inc_counter("tokens_used_total", tokens_used)
        self.histogram("step_duration_seconds", duration, labels)

    def request_metrics(
        self, endpoint: str, method: str, status_code: int, duration: float
    ) -> None:
        """Record HTTP request metrics."""
        labels = {"endpoint": endpoint, "method": method, "status": str(status_code)}

        self.inc_counter("requests_total", 1, labels)
        self.histogram("request_duration_seconds", duration, labels)

        if status_code >= 400:
            self.inc_counter(
                "requests_failed", 1, {"endpoint": endpoint, "status": str(status_code)}
            )

    def get_metrics_summary(self) -> dict[str, Any]:
        """Get a summary of all collected metrics."""
        with self._lock:
            summary = {
                "service": self.service_name,
                "timestamp": time.time(),
                "counters": dict(self._counters),
                "gauges": dict(self._gauges),
                "histograms": {},
                "summaries": {},
            }

            # Calculate histogram statistics
            for name, values in self._histograms.items():
                if values:
                    sorted_values = sorted(values)
                    summary["histograms"][name] = {
                        "count": len(values),
                        "sum": sum(values),
                        "min": min(values),
                        "max": max(values),
                        "mean": sum(values) / len(values),
                        "p50": self._percentile(sorted_values, 0.5),
                        "p90": self._percentile(sorted_values, 0.9),
                        "p95": self._percentile(sorted_values, 0.95),
                        "p99": self._percentile(sorted_values, 0.99),
                    }

            # Calculate summary statistics
            for name, values in self._summaries.items():
                if values:
                    sorted_values = sorted(values)
                    summary["summaries"][name] = {
                        "count": len(values),
                        "sum": sum(values),
                        "mean": sum(values) / len(values),
                        "p50": self._percentile(sorted_values, 0.5),
                        "p90": self._percentile(sorted_values, 0.9),
                        "p95": self._percentile(sorted_values, 0.95),
                        "p99": self._percentile(sorted_values, 0.99),
                    }

        return summary

    def get_prometheus_metrics(self) -> str:
        """Generate Prometheus-formatted metrics."""
        lines = []
        lines.append(f"# CLI Orchestrator Metrics - {self.service_name}")
        lines.append(f"# Generated at: {time.time()}")
        lines.append("")

        with self._lock:
            # Counters
            for metric_key, value in self._counters.items():
                name, labels_str = self._parse_metric_key(metric_key)
                lines.append(f"# TYPE {name} counter")
                lines.append(f"{name}{labels_str} {value}")

            # Gauges
            for metric_key, value in self._gauges.items():
                name, labels_str = self._parse_metric_key(metric_key)
                lines.append(f"# TYPE {name} gauge")
                lines.append(f"{name}{labels_str} {value}")

            # Histograms
            for metric_key, values in self._histograms.items():
                if values:
                    name, labels_str = self._parse_metric_key(metric_key)
                    sorted(values)
                    lines.append(f"# TYPE {name} histogram")

                    # Histogram buckets (simplified)
                    buckets = [0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0]
                    cumulative_count = 0

                    for bucket in buckets:
                        count = len([v for v in values if v <= bucket])
                        cumulative_count = max(cumulative_count, count)
                        bucket_labels = (
                            labels_str.replace("}", f',le="{bucket}"}}')
                            if labels_str != ""
                            else f'{{le="{bucket}"}}'
                        )
                        lines.append(f"{name}_bucket{bucket_labels} {count}")

                    # +Inf bucket
                    inf_labels = (
                        labels_str.replace("}", ',le="+Inf"}')
                        if labels_str != ""
                        else '{le="+Inf"}'
                    )
                    lines.append(f"{name}_bucket{inf_labels} {len(values)}")

                    # Count and sum
                    lines.append(f"{name}_count{labels_str} {len(values)}")
                    lines.append(f"{name}_sum{labels_str} {sum(values)}")

        return "\n".join(lines)

    def _make_metric_key(
        self, name: str, labels: Optional[dict[str, str]] = None
    ) -> str:
        """Create a unique key for a metric with labels."""
        if not labels:
            return name

        sorted_labels = sorted(labels.items())
        label_str = ",".join([f"{k}={v}" for k, v in sorted_labels])
        return f"{name}{{{label_str}}}"

    def _parse_metric_key(self, metric_key: str) -> tuple[str, str]:
        """Parse a metric key back into name and labels."""
        if "{" not in metric_key:
            return metric_key, ""

        name, labels_part = metric_key.split("{", 1)
        labels_part = labels_part.rstrip("}")

        if not labels_part:
            return name, ""

        return name, f"{{{labels_part}}}"

    @staticmethod
    def _percentile(sorted_values: list[float], percentile: float) -> float:
        """Calculate percentile from sorted values."""
        if not sorted_values:
            return 0.0

        index = int(percentile * (len(sorted_values) - 1))
        return sorted_values[index]

    def reset_metrics(self) -> None:
        """Reset all metrics (useful for testing)."""
        with self._lock:
            self._counters.clear()
            self._gauges.clear()
            self._histograms.clear()
            self._summaries.clear()
            self._counter_labels.clear()
            self._gauge_labels.clear()
