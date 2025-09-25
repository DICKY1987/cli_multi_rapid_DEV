"""
JSON structured logging utilities for CLI Multi Rapid.
"""

import json
import logging
import sys
import time
from typing import Any, Dict, Optional


class JsonFormatter(logging.Formatter):
    """Custom formatter that outputs logs as structured JSON."""

    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON."""

        payload = {
            "ts": int(time.time() * 1000),  # Unix timestamp in milliseconds
            "level": record.levelname,
            "msg": record.getMessage(),
            "logger": record.name,
            "module": record.module,
            "funcName": record.funcName,
            "lineno": record.lineno,
        }

        # Add extra fields if present
        if hasattr(record, "extra"):
            payload["extra"] = record.extra

        # Add exception info if present
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)

        # Add job_id and other workflow context if available
        for attr in ["job_id", "node_id", "phase", "workstream_id"]:
            if hasattr(record, attr):
                payload[attr] = getattr(record, attr)

        return json.dumps(payload, ensure_ascii=False, default=str)


def configure_json_logging(
    level: int = logging.INFO, include_timestamp: bool = True
) -> None:
    """Configure the root logger to use JSON formatting."""

    # Create handler
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.handlers = [handler]
    root_logger.setLevel(level)

    # Prevent duplicate logs
    root_logger.propagate = False


def create_workflow_logger(
    job_id: str, workstream_id: Optional[str] = None, level: int = logging.INFO
) -> logging.Logger:
    """Create a logger with workflow context."""

    logger_name = f"workflow.{job_id}"
    logger = logging.getLogger(logger_name)

    # Don't add handlers if already configured
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(JsonFormatter())
        logger.addHandler(handler)
        logger.setLevel(level)
        logger.propagate = False

    # Add workflow context to all log records
    class WorkflowAdapter(logging.LoggerAdapter):
        def process(self, msg: str, kwargs: Dict[str, Any]) -> tuple:
            extra = kwargs.get("extra", {})
            extra.update({"job_id": job_id, "workstream_id": workstream_id})
            kwargs["extra"] = extra
            return msg, kwargs

    return WorkflowAdapter(logger, {})


def log_with_context(
    logger: logging.Logger, level: int, message: str, **context: Any
) -> None:
    """Log a message with additional context fields."""

    logger.log(level, message, extra=context)


def create_audit_logger(log_file: str = "logs/audit.jsonl") -> logging.Logger:
    """Create a logger specifically for audit events."""

    import pathlib

    # Ensure log directory exists
    pathlib.Path(log_file).parent.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger("audit")

    if not logger.handlers:
        handler = logging.FileHandler(log_file, mode="a", encoding="utf-8")
        handler.setFormatter(JsonFormatter())
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
        logger.propagate = False

    return logger
