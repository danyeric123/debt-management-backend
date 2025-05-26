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
    password: str  # Stored as hashed value
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
    end_date: Optional[str] = None
    description: Optional[str] = None
    creditor: Optional[str] = None
    payment_frequency: str
    payment_amount: Optional[str] = None
    minimum_payment: Optional[str] = None
    current_balance: Optional[str] = None  # Stored as string to preserve precision
    created_at: str
    updated_at: str
    GSI1PK: Optional[str] = None  # For optional GSI1 (e.g., CREDITOR#{creditor})
    GSI1SK: Optional[str] = (
        None  # For optional GSI1 (e.g., USER#{username}#DEBT#{debt_id})
    )
