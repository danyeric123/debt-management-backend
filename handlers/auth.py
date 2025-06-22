"""
Authentication handlers for the debt management API.

This module provides login functionality with JWT token generation,
secure password verification, and Google OAuth integration.
"""

from datetime import datetime, timedelta, timezone

import jwt
from pydantic import ValidationError

from models.users import UserBase
from services.dynamodb import DebtManagementTable
from services.google_oauth import GoogleOAuthService
from services.secrets import get_secret
from utils.decorators import lambda_handler, validate_json_body
from utils.responses import HTTPStatus, error_response, success_response
from utils.security import verify_password

# Initialize shared resources at module level for optimal Lambda performance
# This avoids re-initialization on warm starts and reduces cold start time
table = DebtManagementTable()
google_oauth = GoogleOAuthService()


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

    # Check if user has a password (not OAuth-only user)
    if not user.password:
        return error_response(
            "This account uses Google sign-in. Please sign in with Google.",
            HTTPStatus.BAD_REQUEST,
        )

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
                "avatar_url": user.avatar_url,  # Include avatar URL if available
                "full_name": user.full_name,  # Include full name
            },
            message="Login successful",
        )

    except Exception:
        return error_response(
            "Authentication service temporarily unavailable",
            HTTPStatus.INTERNAL_SERVER_ERROR,
        )


@lambda_handler()
def google_auth_url(event, context):
    """
    Generate Google OAuth authorization URL.

    Returns the URL and state parameter for frontend to initiate OAuth flow.

    Args:
        event: Lambda event object
        context: Lambda context object

    Returns:
        HTTP response with Google OAuth URL and state
    """
    try:
        auth_data = google_oauth.generate_auth_url()

        return success_response(
            data=auth_data, message="Google OAuth URL generated successfully"
        )
    except Exception as e:
        return error_response(
            f"Failed to generate OAuth URL: {str(e)}", HTTPStatus.INTERNAL_SERVER_ERROR
        )


@lambda_handler()
@validate_json_body(required_fields=["code"])
def google_oauth_callback(event, context):
    """
    Handle Google OAuth token exchange from frontend.

    Exchanges authorization code for tokens, validates user info,
    creates or finds user account, and returns JWT token.

    Args:
        event: Lambda event object containing OAuth code from frontend
        context: Lambda context object

    Returns:
        HTTP response with JWT token or error message
    """
    # Extract code from JSON body (sent by frontend)
    body = event["json_body"]
    code = body["code"]

    try:
        # Exchange code for tokens and user info (state is only for CSRF protection, not sent to Google)
        oauth_result = google_oauth.exchange_code_for_tokens(code)
        user_info = oauth_result["user_info"]

        # Extract user profile
        profile = google_oauth.extract_user_profile(user_info)

        # Check if user already exists by Google ID
        existing_user = table.get_user_by_google_id(profile["google_id"])

        if existing_user:
            # User exists, log them in
            username = existing_user.username
        else:
            # Check if user exists by email (account linking)
            existing_user_by_email = table.get_user_by_email(profile["email"])

            if existing_user_by_email:
                # Link Google account to existing user
                existing_user_by_email.google_id = profile["google_id"]
                existing_user_by_email.oauth_provider = "google"
                existing_user_by_email.avatar_url = profile["avatar_url"]
                existing_user_by_email.updated_at = datetime.now(timezone.utc)

                table.update_user(existing_user_by_email)
                username = existing_user_by_email.username
            else:
                # Create new user
                username = _generate_unique_username(profile["suggested_username"])

                new_user = UserBase(
                    username=username,
                    email=profile["email"],
                    full_name=profile["full_name"],
                    google_id=profile["google_id"],
                    oauth_provider="google",
                    avatar_url=profile["avatar_url"],
                    is_email_verified=profile["email_verified"],
                    created_at=datetime.now(timezone.utc),
                    updated_at=datetime.now(timezone.utc),
                )

                table.put_user(new_user)

        # Generate JWT token
        secret = get_secret("AWSCURRENT")

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
                "expires_in": 24 * 3600,
                "avatar_url": profile.get("avatar_url"),
                "full_name": profile.get("full_name"),
            },
            message="Google OAuth login successful",
            status_code=HTTPStatus.OK,
        )

    except ValidationError as e:
        return error_response(
            "User validation failed",
            HTTPStatus.BAD_REQUEST,
            details={"validation_errors": e.errors()},
        )
    except Exception as e:
        # Provide more specific error messages for common OAuth issues
        error_msg = str(e).lower()

        # Parse Google OAuth specific errors
        if "google oauth error:" in error_msg:
            if "invalid_grant" in error_msg:
                if "malformed auth code" in error_msg:
                    return error_response(
                        "Invalid authorization code format. Please try signing in again.",
                        HTTPStatus.BAD_REQUEST,
                    )
                elif (
                    "authorization code used" in error_msg
                    or "code has already been used" in error_msg
                ):
                    return error_response(
                        "This authorization code has already been used. Please try signing in again.",
                        HTTPStatus.BAD_REQUEST,
                    )
                else:
                    return error_response(
                        "Authorization code has expired or is invalid. Please try signing in again.",
                        HTTPStatus.BAD_REQUEST,
                    )
            elif "invalid_client" in error_msg:
                return error_response(
                    "OAuth client configuration error. Please check your Google Cloud Console client ID and secret.",
                    HTTPStatus.INTERNAL_SERVER_ERROR,
                )
            elif "redirect_uri_mismatch" in error_msg:
                return error_response(
                    "OAuth redirect URI mismatch. Please check your Google Cloud Console redirect URI settings.",
                    HTTPStatus.INTERNAL_SERVER_ERROR,
                )
            else:
                return error_response(
                    "Google OAuth error. Please try signing in again.",
                    HTTPStatus.BAD_REQUEST,
                )
        # Fallback for other error types
        elif "invalid_grant" in error_msg:
            return error_response(
                "OAuth authorization code has expired or been used. Please try signing in again.",
                HTTPStatus.BAD_REQUEST,
            )
        elif "token exchange failed" in error_msg:
            return error_response(
                "OAuth token exchange failed. Please try signing in again.",
                HTTPStatus.BAD_REQUEST,
            )
        else:
            return error_response(
                f"OAuth authentication failed: {str(e)}",
                HTTPStatus.INTERNAL_SERVER_ERROR,
            )


def _generate_unique_username(suggested_username: str) -> str:
    """
    Generate a unique username by checking database and adding suffix if needed.

    Args:
        suggested_username: Base username from email

    Returns:
        Unique username
    """
    base_username = suggested_username
    counter = 1
    username = base_username

    # Keep trying until we find a unique username
    while table.get_user(username):
        username = f"{base_username}{counter}"
        counter += 1

        # Prevent infinite loop
        if counter > 1000:
            raise ValueError("Unable to generate unique username")

    return username
