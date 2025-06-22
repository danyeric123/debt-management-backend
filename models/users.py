from datetime import datetime
from typing import Any, Dict

import pydantic
from pydantic import BaseModel, EmailStr, Field, SecretStr

from models.dynamodb import UserItem


class UserBase(BaseModel):
    """Base model for user data."""

    username: str = Field(..., min_length=3, max_length=50)
    email: EmailStr
    full_name: str = Field(..., min_length=3, max_length=100)
    password: SecretStr | None = Field(None, min_length=8)  # Optional for OAuth users
    google_id: str | None = None  # Google OAuth ID
    oauth_provider: str | None = None  # "google", "password", or None for legacy users
    avatar_url: str | None = None  # Profile picture URL from OAuth provider
    is_email_verified: bool = True  # OAuth users have verified emails
    created_at: datetime | None = None
    updated_at: datetime | None = None

    @pydantic.field_validator("username")
    def username_must_not_contain_spaces(cls, v):
        if " " in v:
            raise ValueError("Username must not contain spaces")
        return v

    @pydantic.model_validator(mode="after")
    def validate_auth_method(self):
        """Ensure user has either password or OAuth provider."""
        if not self.password and not self.google_id:
            raise ValueError("User must have either password or OAuth provider")
        return self

    def to_dynamodb_item(self) -> UserItem:
        """Convert to DynamoDB item format."""
        from datetime import timezone

        now = datetime.now(timezone.utc).isoformat()
        created = self.created_at.isoformat() if self.created_at else now
        updated = self.updated_at.isoformat() if self.updated_at else now

        return UserItem(
            PK=f"USER#{self.username}",
            SK="USER#INFO",
            email=self.email,
            full_name=self.full_name,
            password=self.password.get_secret_value() if self.password else None,
            google_id=self.google_id,
            oauth_provider=self.oauth_provider,
            avatar_url=self.avatar_url,
            is_email_verified=self.is_email_verified,
            created_at=created,
            updated_at=updated,
        )

    @classmethod
    def from_dynamodb_item(cls, item: Dict[str, Any]) -> "UserBase":
        """Create a UserBase instance from a DynamoDB item."""
        if not item:
            return None

        # Extract the username from PK format "USER#{username}"
        username = item.get("PK", "").replace("USER#", "") if "PK" in item else ""

        # Handle optional password for OAuth users
        password = item.get("password")

        return cls(
            username=username,
            email=item.get("email", ""),
            full_name=item.get("full_name", ""),
            password=password if password else None,
            google_id=item.get("google_id"),
            oauth_provider=item.get("oauth_provider"),
            avatar_url=item.get("avatar_url"),
            is_email_verified=item.get("is_email_verified", True),
            created_at=(
                datetime.fromisoformat(item.get("created_at"))
                if "created_at" in item
                else None
            ),
            updated_at=(
                datetime.fromisoformat(item.get("updated_at"))
                if "updated_at" in item
                else None
            ),
        )
