"""
Security utilities for password hashing and validation.

This module provides secure password hashing using industry-standard
algorithms and proper salt generation.
"""

import base64
import hashlib
import secrets
from typing import Tuple


class PasswordHasher:
    """
    Secure password hashing using PBKDF2 with SHA-256.

    This implementation uses a random salt for each password and
    a high iteration count for security against brute force attacks.
    """

    # Use a high iteration count for security (100,000+ recommended)
    ITERATIONS = 100_000
    SALT_LENGTH = 32  # 32 bytes = 256 bits

    @classmethod
    def hash_password(cls, password: str) -> str:
        """
        Hash a password with a random salt.

        Args:
            password: Plain text password to hash

        Returns:
            Base64-encoded string containing salt and hash
        """
        # Generate a random salt
        salt = secrets.token_bytes(cls.SALT_LENGTH)

        # Hash the password
        password_hash = hashlib.pbkdf2_hmac(
            "sha256", password.encode("utf-8"), salt, cls.ITERATIONS
        )

        # Combine salt and hash, then base64 encode
        combined = salt + password_hash
        return base64.b64encode(combined).decode("utf-8")

    @classmethod
    def verify_password(cls, password: str, stored_hash: str) -> bool:
        """
        Verify a password against a stored hash.

        Args:
            password: Plain text password to verify
            stored_hash: Base64-encoded stored hash

        Returns:
            True if password matches, False otherwise
        """
        try:
            # Decode the stored hash
            combined = base64.b64decode(stored_hash.encode("utf-8"))

            # Extract salt and hash
            salt = combined[: cls.SALT_LENGTH]
            stored_password_hash = combined[cls.SALT_LENGTH :]

            # Hash the provided password with the same salt
            password_hash = hashlib.pbkdf2_hmac(
                "sha256", password.encode("utf-8"), salt, cls.ITERATIONS
            )

            # Compare hashes using constant-time comparison
            return secrets.compare_digest(password_hash, stored_password_hash)

        except Exception:
            # If any error occurs during verification, return False
            return False

    @classmethod
    def _extract_salt_and_hash(cls, stored_hash: str) -> Tuple[bytes, bytes]:
        """
        Extract salt and hash from stored hash string.

        Args:
            stored_hash: Base64-encoded stored hash

        Returns:
            Tuple of (salt, hash) as bytes
        """
        combined = base64.b64decode(stored_hash.encode("utf-8"))
        salt = combined[: cls.SALT_LENGTH]
        password_hash = combined[cls.SALT_LENGTH :]
        return salt, password_hash


# Convenience functions for backward compatibility
def hash_password(password: str) -> str:
    """Hash a password using secure defaults."""
    return PasswordHasher.hash_password(password)


def verify_password(password: str, stored_hash: str) -> bool:
    """Verify a password against a stored hash."""
    return PasswordHasher.verify_password(password, stored_hash)
