"""Debt model objects for the debt management system."""

import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field

from models.dynamodb import DebtItem


class DebtBase(BaseModel):
    """Base model for debt items."""

    debt_id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="Unique identifier for the debt",
    )
    username: str = Field(..., min_length=3, max_length=50)
    debt_name: str = Field(
        ..., min_length=1, max_length=100, description="User-friendly name for the debt"
    )
    principal: Decimal = Field(..., gt=0)
    interest_rate: Decimal = Field(..., ge=0)
    start_date: datetime
    end_date: Optional[datetime] = None
    description: Optional[str] = None
    creditor: Optional[str] = None
    payment_frequency: str = Field(
        ..., pattern="^(weekly|biweekly|monthly|quarterly|annually)$"
    )
    payment_amount: Optional[Decimal] = Field(None, gt=0)
    minimum_payment: Optional[Decimal] = Field(None, gt=0)
    current_balance: Optional[Decimal] = Field(None, ge=0)
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    def to_dynamodb_item(self) -> DebtItem:
        """Convert to DynamoDB item format."""
        now = datetime.now(timezone.utc).isoformat()
        created = self.created_at.isoformat() if self.created_at else now
        updated = self.updated_at.isoformat() if self.updated_at else now

        return DebtItem(
            PK=f"USER#{self.username}",
            SK=f"DEBT#{self.debt_id}",
            debt_id=self.debt_id,
            debt_name=self.debt_name,
            principal=str(self.principal),
            interest_rate=str(self.interest_rate),
            start_date=self.start_date.isoformat(),
            end_date=self.end_date.isoformat() if self.end_date else None,
            description=self.description,
            creditor=self.creditor,
            payment_frequency=self.payment_frequency,
            payment_amount=str(self.payment_amount) if self.payment_amount else None,
            minimum_payment=str(self.minimum_payment) if self.minimum_payment else None,
            current_balance=str(self.current_balance) if self.current_balance else None,
            created_at=created,
            updated_at=updated,
        )

    @classmethod
    def from_dynamodb_item(cls, item: Dict[str, Any]) -> "DebtBase":
        """Create a DebtBase instance from a DynamoDB item."""
        if not item:
            return None

        # Extract the username from PK format "USER#{username}"
        username = item.get("PK", "").replace("USER#", "") if "PK" in item else ""
        # Extract debt_id from SK format "DEBT#{debt_id}"
        debt_id = (
            item.get("SK", "").replace("DEBT#", "")
            if "SK" in item
            else item.get("debt_id", "")
        )

        return cls(
            debt_id=debt_id,
            username=username,
            debt_name=item.get("debt_name", ""),
            principal=Decimal(item.get("principal", "0")),
            interest_rate=Decimal(item.get("interest_rate", "0")),
            start_date=(
                datetime.fromisoformat(item.get("start_date"))
                if "start_date" in item
                else datetime.now()
            ),
            end_date=(
                datetime.fromisoformat(item.get("end_date"))
                if item.get("end_date")
                else None
            ),
            description=item.get("description"),
            creditor=item.get("creditor"),
            payment_frequency=item.get("payment_frequency", "monthly"),
            payment_amount=(
                Decimal(item.get("payment_amount"))
                if item.get("payment_amount")
                else None
            ),
            minimum_payment=(
                Decimal(item.get("minimum_payment"))
                if item.get("minimum_payment")
                else None
            ),
            current_balance=(
                Decimal(item.get("current_balance"))
                if item.get("current_balance")
                else None
            ),
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


class DebtCreate(BaseModel):
    """Model for creating new debts - excludes auto-generated fields."""

    debt_name: str = Field(
        ..., min_length=1, max_length=100, description="User-friendly name for the debt"
    )
    principal: Decimal = Field(..., gt=0)
    interest_rate: Decimal = Field(..., ge=0)
    start_date: datetime
    end_date: Optional[datetime] = None
    description: Optional[str] = None
    creditor: Optional[str] = None
    payment_frequency: str = Field(
        ..., pattern="^(weekly|biweekly|monthly|quarterly|annually)$"
    )
    payment_amount: Optional[Decimal] = Field(None, gt=0)
    minimum_payment: Optional[Decimal] = Field(None, gt=0)
    current_balance: Optional[Decimal] = Field(None, ge=0)


def debt_item_to_dict(debt_item: DebtItem) -> Dict[str, Any]:
    """Convert a DebtItem to a dictionary for API responses."""
    # Extract username from PK format "USER#{username}"
    username = (
        debt_item.PK.replace("USER#", "") if debt_item.PK.startswith("USER#") else ""
    )

    return {
        "debt_id": debt_item.debt_id,
        "username": username,
        "debt_name": debt_item.debt_name,
        "principal": float(debt_item.principal),
        "interest_rate": float(debt_item.interest_rate),
        "start_date": debt_item.start_date,
        "end_date": debt_item.end_date,
        "description": debt_item.description,
        "creditor": debt_item.creditor,
        "payment_frequency": debt_item.payment_frequency,
        "payment_amount": (
            float(debt_item.payment_amount) if debt_item.payment_amount else None
        ),
        "minimum_payment": (
            float(debt_item.minimum_payment) if debt_item.minimum_payment else None
        ),
        "current_balance": (
            float(debt_item.current_balance) if debt_item.current_balance else None
        ),
        "created_at": debt_item.created_at,
        "updated_at": debt_item.updated_at,
    }
