"""
Utils package for shared utilities and cross-cutting concerns.

This package contains decorators, logging utilities, response formatters,
and security utilities used across the application.
"""

from .decorators import (extract_path_params, lambda_handler, require_auth,
                         validate_json_body)
from .logging import (log_error, log_lambda_event, log_lambda_response,
                      setup_logger)
from .responses import (HTTPStatus, error_response, not_found_response,
                        success_response, validation_error_response)
from .security import hash_password, verify_password

__all__ = [
    # Decorators
    "lambda_handler",
    "require_auth",
    "validate_json_body",
    "extract_path_params",
    # Logging
    "setup_logger",
    "log_lambda_event",
    "log_lambda_response",
    "log_error",
    # Responses
    "HTTPStatus",
    "success_response",
    "error_response",
    "validation_error_response",
    "not_found_response",
    # Security
    "hash_password",
    "verify_password",
]
