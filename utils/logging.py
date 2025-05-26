"""
Centralized logging configuration for the debt management backend.

This module provides consistent logging setup across all Lambda functions
with proper formatting, log levels, and structured logging capabilities.
"""

import json
import logging
import sys
from datetime import datetime
from typing import Any, Dict, Optional


class StructuredFormatter(logging.Formatter):
    """
    Custom formatter that outputs structured JSON logs for better CloudWatch parsing.
    """

    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        # Add exception info if present
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)

        # Add any extra fields from the log record
        for key, value in record.__dict__.items():
            if key not in {
                "name",
                "msg",
                "args",
                "levelname",
                "levelno",
                "pathname",
                "filename",
                "module",
                "exc_info",
                "exc_text",
                "stack_info",
                "lineno",
                "funcName",
                "created",
                "msecs",
                "relativeCreated",
                "thread",
                "threadName",
                "processName",
                "process",
                "getMessage",
            }:
                log_entry[key] = value

        return json.dumps(log_entry, default=str)


def setup_logger(
    name: str, level: str = "INFO", structured: bool = True
) -> logging.Logger:
    """
    Set up a logger with consistent configuration.

    Args:
        name: Logger name (typically __name__)
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        structured: Whether to use structured JSON logging

    Returns:
        Configured logger instance
    """
    logger = logging.getLogger(name)

    # Avoid duplicate handlers
    if logger.handlers:
        return logger

    logger.setLevel(getattr(logging, level.upper()))

    # Create console handler
    handler = logging.StreamHandler(sys.stdout)

    if structured:
        formatter = StructuredFormatter()
    else:
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )

    handler.setFormatter(formatter)
    logger.addHandler(handler)

    # Prevent propagation to avoid duplicate logs
    logger.propagate = False

    return logger


def log_lambda_event(
    logger: logging.Logger, event: Dict[str, Any], context: Any
) -> None:
    """
    Log Lambda event details in a structured way.

    Args:
        logger: Logger instance
        event: Lambda event
        context: Lambda context
    """
    logger.info(
        "Lambda invocation started",
        extra={
            "request_id": getattr(context, "aws_request_id", "unknown"),
            "function_name": getattr(context, "function_name", "unknown"),
            "function_version": getattr(context, "function_version", "unknown"),
            "remaining_time_ms": getattr(
                context, "get_remaining_time_in_millis", lambda: 0
            )(),
            "http_method": event.get("httpMethod")
            or event.get("requestContext", {}).get("http", {}).get("method"),
            "path": event.get("path") or event.get("rawPath"),
            "user_agent": event.get("headers", {}).get("user-agent"),
            "source_ip": event.get("requestContext", {})
            .get("http", {})
            .get("sourceIp"),
        },
    )


def log_lambda_response(
    logger: logging.Logger,
    response: Dict[str, Any],
    execution_time_ms: Optional[float] = None,
) -> None:
    """
    Log Lambda response details.

    Args:
        logger: Logger instance
        response: Lambda response
        execution_time_ms: Execution time in milliseconds
    """
    logger.info(
        "Lambda invocation completed",
        extra={
            "status_code": response.get("statusCode"),
            "execution_time_ms": execution_time_ms,
            "response_size": len(str(response.get("body", ""))),
        },
    )


def log_error(
    logger: logging.Logger, error: Exception, context: Optional[Dict[str, Any]] = None
) -> None:
    """
    Log errors with additional context.

    Args:
        logger: Logger instance
        error: Exception that occurred
        context: Additional context information
    """
    extra = {
        "error_type": type(error).__name__,
        "error_message": str(error),
    }

    if context:
        extra.update(context)

    logger.error(f"Error occurred: {str(error)}", extra=extra, exc_info=True)
