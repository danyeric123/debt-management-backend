"""
User management handlers for the debt management API.

This module provides user retrieval functionality for Supabase-authenticated users.
User creation is handled by Supabase Auth.
"""

from services.dynamodb import dynamodb
from utils.decorators import lambda_handler, require_auth
from utils.responses import (HTTPStatus, error_response, not_found_response,
                             success_response)


@lambda_handler()
@require_auth
def get_user(event, context):
    """
    Get user information from the database.

    Retrieves user data for the authenticated user using the API Gateway authorizer context.

    Args:
        event: Lambda event object (with auth context from authorizer)
        context: Lambda context object

    Returns:
        HTTP response with user data or error message
    """
    # Get username from the authorization context (set by API Gateway authorizer)
    username = event["auth"]["username"]

    # Get user from DynamoDB by username
    user = dynamodb.get_user_by_username(username)
    if not user:
        return not_found_response("User", username)

    # Return user data (excluding sensitive fields)
    user_data = {
        "username": user["username"],
        "email": user["email"],
        "full_name": user["full_name"],
        "supabase_id": user["supabase_id"],
        "avatar_url": user.get("avatar_url"),
        "is_email_verified": user.get("is_email_verified", True),
        "created_at": user["created_at"],
        "updated_at": user["updated_at"],
    }

    return success_response(data=user_data)
