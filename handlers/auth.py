"""
Authentication handlers for the debt management API.

This module provides login functionality with JWT token generation
and secure password verification.
"""

from datetime import datetime, timedelta, timezone

import jwt

from services.dynamodb import DebtManagementTable
from services.secrets import get_secret
from utils.decorators import lambda_handler, validate_json_body
from utils.responses import HTTPStatus, error_response, success_response
from utils.security import verify_password

# Initialize shared resources at module level for optimal Lambda performance
# This avoids re-initialization on warm starts and reduces cold start time
table = DebtManagementTable()


@lambda_handler()
@validate_json_body(required_fields=["username", "password"])
def login(event, context):
    """
    Authenticate user and return JWT token.

    Validates user credentials against the database and returns a JWT token
    for authenticated requests. The token expires after 24 hours.

    Args:
        event: Lambda event object containing login credentials
        context: Lambda context object

    Returns:
        HTTP response with JWT token or error message
    """
    body = event["json_body"]
    username = body["username"]
    password = body["password"]

    # Use shared table instance for optimal performance
    user = table.get_user(username)
    if not user:
        return error_response("Invalid credentials", HTTPStatus.UNAUTHORIZED)

    # Verify password using secure hashing
    stored_password_hash = user.password.get_secret_value()
    if not verify_password(password, stored_password_hash):
        return error_response("Invalid credentials", HTTPStatus.UNAUTHORIZED)

    # Generate JWT token
    try:
        secret = get_secret("AWSCURRENT")  # Always use current version for signing

        payload = {
            "username": username,
            "exp": datetime.now(timezone.utc) + timedelta(hours=24),
            "iat": datetime.now(timezone.utc),
        }

        token = jwt.encode(payload, secret, algorithm="HS256")

        return success_response(
            data={
                "token": token,
                "username": username,
                "expires_in": 24 * 3600,  # 24 hours in seconds
            },
            message="Login successful",
        )

    except Exception:
        return error_response(
            "Authentication service temporarily unavailable",
            HTTPStatus.INTERNAL_SERVER_ERROR,
        )
