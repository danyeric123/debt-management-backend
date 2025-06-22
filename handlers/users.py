"""
User management handlers for the debt management API.

This module provides user creation and retrieval functionality
with proper validation, security, and error handling.
"""

from datetime import datetime, timezone

from pydantic import ValidationError

from models.users import UserBase
from services.dynamodb import DebtManagementTable
from utils.decorators import (extract_path_params, lambda_handler,
                              require_auth, validate_json_body)
from utils.responses import (HTTPStatus, error_response, not_found_response,
                             success_response, validation_error_response)
from utils.security import hash_password

# Initialize shared resources at module level for optimal Lambda performance
# This avoids re-initialization on warm starts and reduces cold start time
table = DebtManagementTable()


@lambda_handler()
@validate_json_body(required_fields=["username", "email", "full_name"])
def create_user(event, context):
    """
    Create a new user in the database.

    Validates user data, hashes the password securely, and stores the user
    in DynamoDB. This endpoint does not require authentication.
    Password is now optional to support OAuth users.

    Args:
        event: Lambda event object containing user data
        context: Lambda context object

    Returns:
        HTTP response with success message or validation errors
    """
    body = event["json_body"]

    # Check if password is provided (traditional registration)
    if "password" not in body or not body["password"]:
        return validation_error_response(
            "Password is required for traditional registration. Use Google OAuth for passwordless signup."
        )

    try:
        # Create and validate user model
        user = UserBase(**body)

        # Hash the password securely
        password_raw = user.password.get_secret_value()
        hashed_password = hash_password(password_raw)

        # Create user with hashed password
        user_dict = user.model_dump()
        user_dict["password"] = hashed_password
        user_dict["oauth_provider"] = "password"  # Mark as password-based user
        user_with_hashed_pw = UserBase(**user_dict)

        # Add timestamps
        now = datetime.now(timezone.utc)
        user_with_hashed_pw.created_at = now
        user_with_hashed_pw.updated_at = now

        # Use shared table instance for optimal performance
        table.put_user(user_with_hashed_pw)

        return success_response(
            data={
                "username": user.username,
                "email": user.email,
                "full_name": user.full_name,
                "oauth_provider": "password",
                "created_at": user_with_hashed_pw.created_at.isoformat(),
            },
            message=f"User {user.username} created successfully",
            status_code=HTTPStatus.CREATED,
        )

    except ValidationError as e:
        return validation_error_response(
            "User validation failed", {"validation_errors": e.errors()}
        )
    except Exception as e:
        # Check for common database errors
        error_str = str(e).lower()
        if "already exists" in error_str or "duplicate" in error_str:
            return error_response(
                f"User {body.get('username', 'unknown')} already exists",
                HTTPStatus.CONFLICT,
            )

        return error_response("Failed to create user", HTTPStatus.INTERNAL_SERVER_ERROR)


@lambda_handler()
@require_auth
@extract_path_params("username")
def get_user(event, context):
    """
    Get user information from the database.

    Retrieves user data for the specified username. Requires authentication
    and users can only access their own data.

    Args:
        event: Lambda event object with username path parameter
        context: Lambda context object

    Returns:
        HTTP response with user data or error message
    """
    username = event["path_params"]["username"]
    auth_username = event["auth"]["username"]

    # Users can only access their own data
    if username != auth_username:
        return error_response(
            "Access denied: You can only access your own user data",
            HTTPStatus.FORBIDDEN,
        )

    # Use shared table instance for optimal performance
    user = table.get_user(username)

    if not user:
        return not_found_response("User", username)

    # Return user data without password
    user_data = user.model_dump(exclude={"password"})

    return success_response(data=user_data)
