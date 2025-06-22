"""DynamoDB data models for the debt management system."""

from typing import Optional

from pydantic import BaseModel


class DynamoDBItem(BaseModel):
    """Base class for all DynamoDB items."""

    PK: str
    SK: str


class UserItem(DynamoDBItem):
    """Represents a user item in DynamoDB."""

    PK: str  # USER#{username}
    SK: str = "USER#INFO"
    email: str
    full_name: str
    password: str | None = None  # Stored as hashed value, optional for OAuth users
    google_id: str | None = None  # Google OAuth ID
    oauth_provider: str | None = None  # "google", "password", or None for legacy users
    avatar_url: str | None = None  # Profile picture URL from OAuth provider
    is_email_verified: bool = True  # OAuth users have verified emails
    created_at: str
    updated_at: str


class DebtItem(DynamoDBItem):
    """Represents a debt item in DynamoDB."""

    PK: str  # USER#{username}
    SK: str  # DEBT#{debt_id}
    debt_id: str  # Unique identifier for the debt
    debt_name: str  # User-friendly name for the debt
    principal: str  # Stored as string to preserve precision
    interest_rate: str  # Stored as string to preserve precision
    start_date: str
    end_date: str | None = None
    description: str | None = None
    creditor: str | None = None
    payment_frequency: str
    payment_amount: str | None = None
    minimum_payment: str | None = None
    current_balance: str | None = None  # Stored as string to preserve precision
    created_at: str
    updated_at: str
    GSI1PK: str | None = None  # For optional GSI1 (e.g., CREDITOR#{creditor})
    GSI1SK: str | None = (
        None  # For optional GSI1 (e.g., USER#{username}#DEBT#{debt_id})
    )
