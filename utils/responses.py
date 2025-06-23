"""
Standardized HTTP response utilities for Lambda functions.

This module provides consistent response formatting, error handling,
and JSON serialization across all API endpoints.
"""

import json
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, Optional, Union


class HTTPStatus(Enum):
    """HTTP status codes for API responses."""

    OK = 200
    CREATED = 201
    BAD_REQUEST = 400
    UNAUTHORIZED = 401
    FORBIDDEN = 403
    NOT_FOUND = 404
    CONFLICT = 409
    INTERNAL_SERVER_ERROR = 500


# CORS headers for API responses
cors_headers = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Headers": "Content-Type,Authorization",
    "Access-Control-Allow-Methods": "GET,POST,PUT,DELETE,OPTIONS",
}


class APIJSONEncoder(json.JSONEncoder):
    """
    Custom JSON encoder for API responses that handles:
    - Decimal objects (from DynamoDB)
    - datetime objects
    - Other common Python types
    """

    def default(self, obj: Any) -> Any:
        if isinstance(obj, Decimal):
            return float(obj)
        if isinstance(obj, datetime):
            return obj.isoformat()
        if hasattr(obj, "model_dump"):  # Pydantic models
            return obj.model_dump()
        return super().default(obj)


def create_response(
    status_code: Union[int, HTTPStatus],
    body: Any = None,
    headers: Optional[Dict[str, str]] = None,
    cors_enabled: bool = True,
) -> Dict[str, Any]:
    """
    Create a standardized Lambda HTTP response.

    Args:
        status_code: HTTP status code
        body: Response body (will be JSON serialized)
        headers: Additional headers
        cors_enabled: Whether to include CORS headers

    Returns:
        Lambda HTTP response dictionary
    """
    if isinstance(status_code, HTTPStatus):
        status_code = status_code.value

    response_headers = {}

    if cors_enabled:
        response_headers.update(cors_headers)

    if headers:
        response_headers.update(headers)

    response = {
        "statusCode": status_code,
        "headers": response_headers,
    }

    if body is not None:
        if isinstance(body, (dict, list)) or hasattr(body, "model_dump"):
            response["body"] = json.dumps(body, cls=APIJSONEncoder)
        else:
            response["body"] = str(body)

    return response


def success_response(
    data: Any = None,
    message: Optional[str] = None,
    status_code: Union[int, HTTPStatus] = HTTPStatus.OK,
) -> Dict[str, Any]:
    """
    Create a success response.

    Args:
        data: Response data
        message: Success message
        status_code: HTTP status code

    Returns:
        Lambda HTTP response dictionary
    """
    body = {}

    if message:
        body["message"] = message

    if data is not None:
        if isinstance(data, dict):
            body.update(data)
        else:
            body["data"] = data

    return create_response(status_code, body)


def error_response(
    message: str,
    status_code: Union[int, HTTPStatus] = HTTPStatus.INTERNAL_SERVER_ERROR,
    error_code: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Create an error response.

    Args:
        message: Error message
        status_code: HTTP status code
        error_code: Application-specific error code
        details: Additional error details

    Returns:
        Lambda HTTP response dictionary
    """
    body = {"error": message}

    if error_code:
        body["error_code"] = error_code

    if details:
        body["details"] = details

    return create_response(status_code, body)


def validation_error_response(
    message: str = "Validation failed", errors: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Create a validation error response.

    Args:
        message: Error message
        errors: Validation error details

    Returns:
        Lambda HTTP response dictionary
    """
    return error_response(
        message=message,
        status_code=HTTPStatus.BAD_REQUEST,
        error_code="VALIDATION_ERROR",
        details=errors,
    )


def not_found_response(
    resource: str, identifier: Optional[str] = None
) -> Dict[str, Any]:
    """
    Create a not found error response.

    Args:
        resource: Resource type (e.g., "User", "Debt")
        identifier: Resource identifier

    Returns:
        Lambda HTTP response dictionary
    """
    if identifier:
        message = f"{resource} '{identifier}' not found"
    else:
        message = f"{resource} not found"

    return error_response(
        message=message,
        status_code=HTTPStatus.NOT_FOUND,
        error_code="RESOURCE_NOT_FOUND",
    )


def unauthorized_response(message: str = "Unauthorized access") -> Dict[str, Any]:
    """
    Create an unauthorized error response.

    Args:
        message: Error message

    Returns:
        Lambda HTTP response dictionary
    """
    return error_response(
        message=message, status_code=HTTPStatus.UNAUTHORIZED, error_code="UNAUTHORIZED"
    )
