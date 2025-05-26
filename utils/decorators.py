"""
Decorators for Lambda function handlers.

This module provides decorators that add consistent logging, error handling,
and response formatting to Lambda functions.
"""

import json
import time
from functools import wraps
from typing import Any, Callable, Dict, Optional

from .logging import (log_error, log_lambda_event, log_lambda_response,
                      setup_logger)
from .responses import HTTPStatus, error_response


def lambda_handler(
    logger_name: Optional[str] = None,
    log_event: bool = True,
    log_response: bool = True,
    structured_logging: bool = True,
) -> Callable:
    """
    Decorator for Lambda function handlers that provides:
    - Consistent logging setup
    - Automatic event/response logging
    - Error handling and response formatting
    - Execution time tracking

    Args:
        logger_name: Logger name (defaults to function module name)
        log_event: Whether to log incoming events
        log_response: Whether to log responses
        structured_logging: Whether to use structured JSON logging

    Returns:
        Decorated function
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
            # Set up logger
            logger = setup_logger(
                logger_name or func.__module__, structured=structured_logging
            )

            start_time = time.time()

            try:
                # Log incoming event
                if log_event:
                    log_lambda_event(logger, event, context)

                # Call the actual handler
                response = func(event, context)

                # Ensure response is properly formatted
                if not isinstance(response, dict) or "statusCode" not in response:
                    logger.warning("Handler returned invalid response format")
                    response = error_response(
                        "Internal server error", HTTPStatus.INTERNAL_SERVER_ERROR
                    )

                # Log response
                if log_response:
                    execution_time = (time.time() - start_time) * 1000
                    log_lambda_response(logger, response, execution_time)

                return response

            except Exception as e:
                execution_time = (time.time() - start_time) * 1000

                # Log the error with context
                log_error(
                    logger,
                    e,
                    {
                        "function_name": getattr(context, "function_name", "unknown"),
                        "request_id": getattr(context, "aws_request_id", "unknown"),
                        "execution_time_ms": execution_time,
                        "event_path": event.get("path") or event.get("rawPath"),
                        "event_method": event.get("httpMethod")
                        or event.get("requestContext", {})
                        .get("http", {})
                        .get("method"),
                    },
                )

                # Return standardized error response
                return error_response(
                    "Internal server error", HTTPStatus.INTERNAL_SERVER_ERROR
                )

        return wrapper

    return decorator


def require_auth(func: Callable) -> Callable:
    """
    Decorator that ensures the request is authenticated.

    This decorator checks for authorization context that should be
    set by the API Gateway authorizer.

    Args:
        func: Function to decorate

    Returns:
        Decorated function
    """

    @wraps(func)
    def wrapper(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
        # Check for authorization context from API Gateway authorizer
        # For HTTP API Gateway, context is in requestContext.authorizer.lambda
        request_context = event.get("requestContext", {})
        authorizer_context = request_context.get("authorizer", {})

        # Try both REST API and HTTP API formats
        auth_context = authorizer_context.get("lambda", authorizer_context)

        if not auth_context or not auth_context.get("username"):
            # Debug: log the event structure to understand what's available
            from .logging import setup_logger

            logger = setup_logger(__name__)
            logger.info(
                "Authorization failed - no valid context found",
                extra={
                    "request_context_keys": list(request_context.keys()),
                    "authorizer_keys": list(authorizer_context.keys()),
                    "auth_context": auth_context,
                    "event_keys": list(event.keys()),
                },
            )
            return error_response("Unauthorized access", HTTPStatus.UNAUTHORIZED)

        # Add auth info to event for easy access in handlers
        event["auth"] = {
            "username": auth_context.get("username"),
            "user_id": auth_context.get("userId"),
        }

        return func(event, context)

    return wrapper


def validate_json_body(required_fields: Optional[list] = None) -> Callable:
    """
    Decorator that validates and parses JSON request body.

    Args:
        required_fields: List of required field names

    Returns:
        Decorated function
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
            try:
                # Parse JSON body
                body_str = event.get("body", "{}")
                if not body_str:
                    body_str = "{}"

                body = json.loads(body_str)
                event["json_body"] = body

                # Validate required fields
                if required_fields:
                    missing_fields = [
                        field
                        for field in required_fields
                        if field not in body or body[field] is None
                    ]

                    if missing_fields:
                        from .responses import validation_error_response

                        return validation_error_response(
                            f"Missing required fields: {', '.join(missing_fields)}",
                            {"missing_fields": missing_fields},
                        )

                return func(event, context)

            except json.JSONDecodeError as e:
                from .responses import validation_error_response

                return validation_error_response(
                    "Invalid JSON in request body", {"json_error": str(e)}
                )

        return wrapper

    return decorator


def extract_path_params(*param_names: str) -> Callable:
    """
    Decorator that extracts and validates path parameters.

    Args:
        param_names: Names of path parameters to extract

    Returns:
        Decorated function
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
            path_params = event.get("pathParameters") or {}

            # Check for missing parameters
            missing_params = [
                param
                for param in param_names
                if param not in path_params or not path_params[param]
            ]

            if missing_params:
                from .responses import validation_error_response

                return validation_error_response(
                    f"Missing path parameters: {', '.join(missing_params)}",
                    {"missing_parameters": missing_params},
                )

            # Add extracted params to event for easy access
            event["path_params"] = {param: path_params[param] for param in param_names}

            return func(event, context)

        return wrapper

    return decorator
