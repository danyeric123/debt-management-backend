"""
Google OAuth service for handling authentication flows.

This module provides secure Google OAuth 2.0 integration following best practices
from Google's documentation. Configuration is loaded from AWS Parameter Store.
"""

import secrets
import urllib.parse
from typing import Any, Dict

import requests
from google.auth.exceptions import GoogleAuthError
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token

from services.parameter_store import config
from utils.logging import setup_logger

logger = setup_logger(__name__)


class GoogleOAuthService:
    """
    Secure Google OAuth 2.0 service following best practices.

    Handles authorization URL generation, token exchange, and ID token validation.
    Configuration is loaded from AWS Parameter Store with local .env fallback.
    """

    def __init__(self):
        """Initialize OAuth service with configuration from Parameter Store."""
        try:
            oauth_config = config.load_oauth_config()
            self.client_id = oauth_config["client_id"]
            self.client_secret = oauth_config["client_secret"]
            self.redirect_uri = oauth_config["redirect_uri"]
        except ValueError as e:
            logger.error(f"Failed to load OAuth configuration: {e}")
            raise

        # OAuth 2.0 endpoints
        self.auth_url = "https://accounts.google.com/o/oauth2/v2/auth"
        self.token_url = "https://oauth2.googleapis.com/token"

        # Required scopes for user information
        self.scopes = ["openid", "email", "profile"]

    def generate_auth_url(self, state: str | None = None) -> Dict[str, str]:
        """
        Generate Google OAuth authorization URL with security parameters.

        Args:
            state: Optional state parameter for CSRF protection

        Returns:
            Dictionary with auth_url and state
        """
        if not state:
            state = secrets.token_urlsafe(32)  # Generate secure random state

        params = {
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "scope": " ".join(self.scopes),
            "response_type": "code",
            "state": state,
            "access_type": "offline",  # For refresh tokens if needed
            "prompt": "consent",  # Force consent to get refresh token
            "include_granted_scopes": "true",
        }

        auth_url = f"{self.auth_url}?{urllib.parse.urlencode(params)}"

        logger.info(
            "Generated OAuth authorization URL",
            extra={
                "state": state,
                "scopes": self.scopes,
                "client_id": self.client_id,
                "redirect_uri": self.redirect_uri,
                "auth_url_length": len(auth_url),
                "auth_url": auth_url,  # Log the full URL for debugging
                "params": params,
            },
        )

        return {"auth_url": auth_url, "state": state}

    def exchange_code_for_tokens(self, code: str) -> Dict[str, Any]:
        """
        Exchange authorization code for access and ID tokens.

        Args:
            code: Authorization code from Google

        Returns:
            Dictionary containing tokens and user info

        Raises:
            ValueError: If token exchange fails
            GoogleAuthError: If ID token validation fails
        """
        try:
            # Exchange code for tokens
            token_data = {
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "code": code,
                "grant_type": "authorization_code",
                "redirect_uri": self.redirect_uri,
            }

            logger.info(
                "Attempting token exchange with Google",
                extra={
                    "client_id": self.client_id,
                    "redirect_uri": self.redirect_uri,
                    "code_length": len(code),
                    "code_preview": code[:20] + "..." if len(code) > 20 else code,
                },
            )

            response = requests.post(
                self.token_url,
                data=token_data,
                headers={"Accept": "application/json"},
                timeout=10,
            )

            logger.info(
                "Google token exchange response received",
                extra={
                    "status_code": response.status_code,
                    "response_headers": dict(response.headers),
                    "response_length": len(response.text),
                },
            )

            if not response.ok:
                # Try to parse Google's error response
                error_type = "unknown"
                error_description = ""
                full_response = response.text

                try:
                    error_data = response.json()
                    error_type = error_data.get("error", "unknown")
                    error_description = error_data.get("error_description", "")
                    logger.error(
                        "Google OAuth error response parsed",
                        extra={
                            "error_type": error_type,
                            "error_description": error_description,
                            "full_error_data": error_data,
                        },
                    )
                except Exception as parse_error:
                    # If JSON parsing fails, log the raw response
                    logger.error(
                        "Failed to parse Google error response as JSON",
                        extra={
                            "parse_error": str(parse_error),
                            "raw_response": full_response,
                        },
                    )

                logger.error(
                    "Token exchange failed",
                    extra={
                        "status_code": response.status_code,
                        "error_type": error_type,
                        "error_description": error_description,
                        "response": full_response,
                        "request_data": {
                            "client_id": self.client_id,
                            "redirect_uri": self.redirect_uri,
                            "code_length": len(code),
                        },
                    },
                )

                # Raise with specific Google error details if available
                if error_type != "unknown" and error_description:
                    raise ValueError(
                        f"Google OAuth error: {error_type} - {error_description}"
                    )
                else:
                    raise ValueError(
                        f"Token exchange failed with status {response.status_code}: {full_response}"
                    )

            tokens = response.json()

            # Validate and decode ID token
            id_token_jwt = tokens.get("id_token")
            if not id_token_jwt:
                raise ValueError("No ID token received from Google")

            # Verify ID token signature and claims
            user_info = id_token.verify_oauth2_token(
                id_token_jwt,
                google_requests.Request(),
                self.client_id,
                clock_skew_in_seconds=10,
            )

            # Additional security checks
            if user_info.get("aud") != self.client_id:
                raise GoogleAuthError("Invalid audience in ID token")

            if user_info.get("iss") not in [
                "accounts.google.com",
                "https://accounts.google.com",
            ]:
                raise GoogleAuthError("Invalid issuer in ID token")

            logger.info(
                "Successfully validated Google ID token",
                extra={
                    "user_id": user_info.get("sub"),
                    "email": user_info.get("email"),
                    "email_verified": user_info.get("email_verified"),
                },
            )

            return {
                "access_token": tokens.get("access_token"),
                "refresh_token": tokens.get("refresh_token"),
                "id_token": id_token_jwt,
                "user_info": user_info,
                "expires_in": tokens.get("expires_in"),
            }

        except GoogleAuthError as e:
            logger.error(
                "Google Auth error during token validation", extra={"error": str(e)}
            )
            raise
        except Exception as e:
            logger.error(
                "Unexpected error during token exchange", extra={"error": str(e)}
            )
            raise ValueError(f"Token exchange failed: {str(e)}")

    def extract_user_profile(self, user_info: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract and validate user profile information from Google ID token.

        Args:
            user_info: Decoded ID token payload

        Returns:
            Normalized user profile data
        """
        if not user_info.get("email_verified", False):
            raise ValueError("Google account email is not verified")

        profile = {
            "google_id": user_info.get("sub"),  # Google's unique user ID
            "email": user_info.get("email"),
            "full_name": user_info.get("name", ""),
            "given_name": user_info.get("given_name", ""),
            "family_name": user_info.get("family_name", ""),
            "avatar_url": user_info.get("picture"),
            "locale": user_info.get("locale"),
            "email_verified": user_info.get("email_verified", False),
        }

        # Generate username from email (can be customized)
        email_username = profile["email"].split("@")[0]
        # Clean username to meet requirements (no spaces, length limits)
        username = email_username.replace(".", "").replace("+", "")[:50]
        profile["suggested_username"] = username

        logger.info(
            "Extracted user profile from Google",
            extra={
                "google_id": profile["google_id"],
                "email": profile["email"],
                "suggested_username": username,
            },
        )

        return profile
