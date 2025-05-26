from datetime import datetime
from typing import Any, Dict, Optional

import pydantic
from pydantic import BaseModel, EmailStr, Field, SecretStr

from models.dynamodb import UserItem


class UserBase(BaseModel):
    """Base model for user data."""

    username: str = Field(..., min_length=3, max_length=50)
    email: EmailStr
    full_name: str = Field(..., min_length=3, max_length=100)
    password: SecretStr = Field(..., min_length=8)
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    @pydantic.field_validator("username")
    def username_must_not_contain_spaces(cls, v):
        if " " in v:
            raise ValueError("Username must not contain spaces")
        return v

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
            password=self.password.get_secret_value(),  # Only extract raw password when storing to DB
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

        return cls(
            username=username,
            email=item.get("email", ""),
            full_name=item.get("full_name", ""),
            password=item.get("password", ""),  # This will be wrapped in SecretStr
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
