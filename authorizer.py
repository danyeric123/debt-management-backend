"""
JWT Authorization Lambda for API Gateway.

This module provides JWT token validation for protected API endpoints.
It validates tokens against AWS Secrets Manager and verifies user existence
in the database.
"""

from typing import Any, Dict, Optional

import jwt

from services.dynamodb import DebtManagementTable
from services.secrets import get_all_secret_versions
from utils.logging import log_error, setup_logger

# Initialize shared resources at module level for optimal Lambda performance
# This avoids re-initialization on warm starts and reduces cold start time
logger = setup_logger(__name__)
table = DebtManagementTable()


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    HTTP API Gateway Lambda Authorizer.

    Validates JWT tokens and returns authorization decisions for API Gateway.
    For HTTP API Gateway, returns {"isAuthorized": True/False} with optional context.

    Args:
        event: API Gateway authorizer event
        context: Lambda context object

    Returns:
        Authorization response for API Gateway
    """
    logger.info(
        "Authorization request received",
        extra={
            "request_id": getattr(context, "aws_request_id", "unknown"),
            "method": event.get("requestContext", {}).get("http", {}).get("method"),
            "path": event.get("rawPath"),
            "headers": event.get("headers", {}),
            "event_keys": list(event.keys()),
        },
    )

    try:
        # Extract and validate authorization header
        token = _extract_token_from_event(event)
        if not token:
            logger.info(
                "No valid authorization token found",
                extra={"headers": event.get("headers", {})},
            )
            return {"isAuthorized": False}

        # Validate JWT token
        payload = _validate_jwt_token(token)
        if not payload:
            logger.info("JWT token validation failed")
            return {"isAuthorized": False}

        # Validate user exists in database
        username = payload.get("username")
        if not username:
            logger.info("No username found in token payload")
            return {"isAuthorized": False}

        if not _validate_user_exists(username):
            logger.info("User not found in database", extra={"username": username})
            return {"isAuthorized": False}

        logger.info("User authorized successfully", extra={"username": username})

        # Return authorization success with context
        return {
            "isAuthorized": True,
            "context": {
                "username": username,
                "userId": f"USER#{username}",
                "principalId": username,  # Required for HTTP API Gateway
            },
        }

    except Exception as e:
        log_error(
            logger,
            e,
            {
                "event_path": event.get("rawPath"),
                "event_method": event.get("requestContext", {})
                .get("http", {})
                .get("method"),
            },
        )
        return {"isAuthorized": False}


def _extract_token_from_event(event: Dict[str, Any]) -> Optional[str]:
    """
    Extract JWT token from the Authorization header.

    Args:
        event: API Gateway event

    Returns:
        JWT token string or None if not found/invalid
    """
    headers = event.get("headers", {})

    # Find Authorization header (case-insensitive)
    auth_header = None
    for key, value in headers.items():
        if key.lower() == "authorization":
            auth_header = value
            break

    if not auth_header:
        return None

    # Extract token from "Bearer <token>" format
    if not auth_header.startswith("Bearer "):
        return None

    token = auth_header[7:]  # Remove "Bearer " prefix

    if not token:
        return None

    logger.debug("Token extracted successfully", extra={"token_prefix": token[:20]})
    return token


def _validate_jwt_token(token: str) -> Optional[Dict[str, Any]]:
    """
    Validate JWT token against available secrets.

    Args:
        token: JWT token string

    Returns:
        Token payload if valid, None otherwise
    """
    try:
        secrets = get_all_secret_versions()

        for secret in secrets:
            try:
                payload = jwt.decode(token, key=secret, algorithms=["HS256"])
                logger.debug("JWT token validated successfully")
                return payload
            except jwt.ExpiredSignatureError:
                logger.info("JWT token has expired")
                return None
            except jwt.InvalidTokenError:
                # Try next secret version
                continue

        logger.info("JWT token validation failed with all available secrets")
        return None

    except Exception as e:
        logger.error("Error during JWT validation", extra={"error": str(e)})
        return None


def _validate_user_exists(username: str) -> bool:
    """
    Validate that the user exists in the database.

    Args:
        username: Username to validate

    Returns:
        True if user exists, False otherwise
    """
    try:
        # Use shared table instance for optimal performance
        user = table.get_user(username)

        if not user:
            return False

        # Additional validation: ensure username matches
        if user.username != username:
            logger.warning(
                "Username mismatch in database",
                extra={"token_username": username, "db_username": user.username},
            )
            return False

        return True

    except Exception as e:
        logger.error(
            "Error validating user existence",
            extra={"username": username, "error": str(e)},
        )
        return False
