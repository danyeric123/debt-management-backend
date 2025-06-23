"""
Supabase authentication service for validating JWT tokens
"""

import logging
import os
from typing import Any, Dict, Optional

import jwt
from jwt.exceptions import ExpiredSignatureError, InvalidTokenError

logger = logging.getLogger(__name__)


class SupabaseAuth:
    def __init__(self):
        self.supabase_url = os.getenv("SUPABASE_URL")
        self.supabase_jwt_secret = os.getenv("SUPABASE_JWT_SECRET")
        self.supabase_anon_key = os.getenv(
            "SUPABASE_ANON_KEY"
        )  # Add anon key for API calls

        if not self.supabase_url:
            logger.warning("Supabase URL not configured")

        if not self.supabase_jwt_secret:
            logger.warning(
                "Supabase JWT secret not configured. Will use API-based verification."
            )

    def validate_jwt_token(self, token: str) -> Optional[Dict[str, Any]]:
        """
        Validate a Supabase JWT token and return user information

        Args:
            token: The JWT token from the Authorization header

        Returns:
            Dictionary containing user information if valid, None otherwise
        """
        # Try manual JWT verification first (if secret is available)
        if self.supabase_jwt_secret:
            return self._validate_jwt_manual(token)

        # Fallback to API-based verification
        logger.info("Using API-based token verification (no JWT secret available)")
        return self._validate_jwt_via_api(token)

    def _validate_jwt_manual(self, token: str) -> Optional[Dict[str, Any]]:
        """Manual JWT verification using the JWT secret"""
        try:
            if not self.supabase_jwt_secret:
                logger.error("Supabase JWT secret not configured")
                return None

            # Decode and verify the JWT token
            payload = jwt.decode(
                token,
                self.supabase_jwt_secret,
                algorithms=["HS256"],
                audience="authenticated",
            )

            # Extract user information from the payload
            user_info = {
                "supabase_id": payload.get("sub"),
                "email": payload.get("email"),
                "email_verified": payload.get("email_confirmed_at") is not None,
                "provider": payload.get("app_metadata", {}).get("provider"),
                "user_metadata": payload.get("user_metadata", {}),
                "aud": payload.get("aud"),
                "exp": payload.get("exp"),
                "iat": payload.get("iat"),
                "iss": payload.get("iss"),
            }

            logger.info(f"Successfully validated token for user: {user_info['email']}")
            return user_info

        except ExpiredSignatureError:
            logger.warning("JWT token has expired")
            return None
        except InvalidTokenError as e:
            logger.warning(f"Invalid JWT token: {str(e)}")
            return None
        except Exception as e:
            logger.error(f"Error validating JWT token: {str(e)}")
            return None

    def _validate_jwt_via_api(self, token: str) -> Optional[Dict[str, Any]]:
        """
        Alternative: Validate JWT token by calling Supabase API
        This method works without needing the JWT secret
        """
        try:
            import requests

            if not self.supabase_url or not self.supabase_anon_key:
                logger.error(
                    "Supabase URL or anon key not configured for API verification"
                )
                return None

            # Call Supabase auth API to verify the token
            headers = {
                "Authorization": f"Bearer {token}",
                "apikey": self.supabase_anon_key,
                "Content-Type": "application/json",
            }

            response = requests.get(
                f"{self.supabase_url}/auth/v1/user", headers=headers, timeout=10
            )

            if response.status_code == 200:
                user_data = response.json()

                # Convert to our expected format
                user_info = {
                    "supabase_id": user_data.get("id"),
                    "email": user_data.get("email"),
                    "email_verified": user_data.get("email_confirmed_at") is not None,
                    "provider": user_data.get("app_metadata", {}).get("provider"),
                    "user_metadata": user_data.get("user_metadata", {}),
                    "aud": user_data.get("aud"),
                    "exp": None,  # Not provided by API
                    "iat": None,  # Not provided by API
                    "iss": "supabase",
                }

                logger.info(
                    f"Successfully validated token via API for user: {user_info['email']}"
                )
                return user_info
            else:
                logger.warning(
                    f"Token validation failed via API: {response.status_code}"
                )
                return None

        except Exception as e:
            logger.error(f"Error validating JWT token via API: {str(e)}")
            return None

    def extract_token_from_header(self, authorization_header: str) -> Optional[str]:
        """
        Extract the JWT token from the Authorization header

        Args:
            authorization_header: The Authorization header value

        Returns:
            The JWT token if valid format, None otherwise
        """
        if not authorization_header:
            return None

        parts = authorization_header.split()
        if len(parts) != 2 or parts[0].lower() != "bearer":
            return None

        return parts[1]

    def get_user_from_request(self, event: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Extract and validate user information from Lambda event

        Args:
            event: AWS Lambda event containing headers

        Returns:
            User information if authentication successful, None otherwise
        """
        try:
            headers = event.get("headers", {})
            authorization = headers.get("Authorization") or headers.get("authorization")

            if not authorization:
                logger.debug("No Authorization header found")
                return None

            token = self.extract_token_from_header(authorization)
            if not token:
                logger.debug("Invalid Authorization header format")
                return None

            user_info = self.validate_jwt_token(token)
            return user_info

        except Exception as e:
            logger.error(f"Error extracting user from request: {str(e)}")
            return None


# Global instance
supabase_auth = SupabaseAuth()
