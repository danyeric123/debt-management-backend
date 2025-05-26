"""
DynamoDB service for the debt management system.

This module provides optimized DynamoDB operations with connection pooling
and resource reuse for optimal Lambda performance.
"""

import logging
import os
from typing import List, Optional

import boto3
import botocore

from models.debt import DebtBase
from models.users import UserBase

# Initialize shared resources at module level for optimal Lambda performance
# This avoids re-initialization on warm starts and reduces cold start time
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Create a single DynamoDB resource instance to be reused across all operations
# This provides connection pooling and reduces cold start overhead
_dynamodb_resource = boto3.resource("dynamodb")


class DebtManagementTable:
    """
    Encapsulates operations on the Amazon DynamoDB debt management table.

    Optimized for Lambda environments with shared resource initialization
    and connection pooling for improved performance.
    """

    def __init__(self, table_name: str = None):
        """
        Initialize the DynamoDB table connection using shared resources.

        :param table_name: Name of the DynamoDB table.
        """
        if table_name is None:
            table_name = os.environ.get("TABLE_NAME", "DebtManagementTable")

        # Use the shared DynamoDB resource for optimal performance
        self.table = _dynamodb_resource.Table(table_name)

    def put_user(self, user: UserBase) -> bool:
        """
        Adds a user to the DynamoDB table.

        :param user: The user to add to the table.
        :return: True if successful, raises exception otherwise.
        """
        try:
            ddb_item = user.to_dynamodb_item().model_dump()
            self.table.put_item(Item=ddb_item)
            return True
        except botocore.exceptions.ClientError as err:
            logger.error(
                "Couldn't put user %s in table %s. Error: %s: %s",
                user.username,
                self.table.name,
                err.response["Error"]["Code"],
                err.response["Error"]["Message"],
            )
            raise

    def get_user(self, username: str) -> Optional[UserBase]:
        """
        Gets user data from the table.

        :param username: The username of the user to retrieve.
        :return: The user if found, None otherwise.
        """
        try:
            response = self.table.get_item(
                Key={"PK": f"USER#{username}", "SK": "USER#INFO"}
            )
            item = response.get("Item")
            if not item:
                return None

            return UserBase.from_dynamodb_item(item)
        except botocore.exceptions.ClientError as err:
            logger.error(
                "Couldn't get user %s from table %s. Error: %s: %s",
                username,
                self.table.name,
                err.response["Error"]["Code"],
                err.response["Error"]["Message"],
            )
            raise

    def put_debt(self, debt: DebtBase) -> bool:
        """
        Adds a debt item to the DynamoDB table.

        :param debt: The debt to add to the table.
        :return: True if successful, raises exception otherwise.
        """
        try:
            ddb_item = debt.to_dynamodb_item().model_dump()
            self.table.put_item(Item=ddb_item)
            return True
        except botocore.exceptions.ClientError as err:
            logger.error(
                "Couldn't put debt %s (ID: %s) for user %s in table %s. Error: %s: %s",
                debt.debt_name,
                debt.debt_id,
                debt.username,
                self.table.name,
                err.response["Error"]["Code"],
                err.response["Error"]["Message"],
            )
            raise

    def get_debt(self, username: str, debt_id: str) -> Optional[DebtBase]:
        """
        Gets a specific debt item from the table.

        :param username: The username of the debt owner.
        :param debt_id: The unique ID of the debt to retrieve.
        :return: The debt if found, None otherwise.
        """
        try:
            response = self.table.get_item(
                Key={"PK": f"USER#{username}", "SK": f"DEBT#{debt_id}"}
            )
            item = response.get("Item")
            if not item:
                return None

            return DebtBase.from_dynamodb_item(item)
        except botocore.exceptions.ClientError as err:
            logger.error(
                "Couldn't get debt %s for user %s from table %s. Error: %s: %s",
                debt_id,
                username,
                self.table.name,
                err.response["Error"]["Code"],
                err.response["Error"]["Message"],
            )
            raise

    def list_user_debts(self, username: str) -> List[DebtBase]:
        """
        Lists all debts for a specific user.

        :param username: The username of the debt owner.
        :return: A list of debts associated with the user.
        """
        try:
            response = self.table.query(
                KeyConditionExpression="PK = :pk AND begins_with(SK, :sk_prefix)",
                ExpressionAttributeValues={
                    ":pk": f"USER#{username}",
                    ":sk_prefix": "DEBT#",
                },
            )

            items = response.get("Items", [])
            return [DebtBase.from_dynamodb_item(item) for item in items]
        except botocore.exceptions.ClientError as err:
            logger.error(
                "Couldn't list debts for user %s from table %s. Error: %s: %s",
                username,
                self.table.name,
                err.response["Error"]["Code"],
                err.response["Error"]["Message"],
            )
            raise

    def delete_debt(self, username: str, debt_id: str) -> bool:
        """
        Deletes a specific debt item from the table.

        :param username: The username of the debt owner.
        :param debt_id: The unique ID of the debt to delete.
        :return: True if successful, raises exception otherwise.
        """
        try:
            self.table.delete_item(
                Key={"PK": f"USER#{username}", "SK": f"DEBT#{debt_id}"}
            )
            return True
        except botocore.exceptions.ClientError as err:
            logger.error(
                "Couldn't delete debt %s for user %s from table %s. Error: %s: %s",
                debt_id,
                username,
                self.table.name,
                err.response["Error"]["Code"],
                err.response["Error"]["Message"],
            )
            raise

    def update_debt(self, debt: DebtBase) -> bool:
        """
        Updates an existing debt item in the table.

        :param debt: The debt with updated information.
        :return: True if successful, raises exception otherwise.
        """
        # Simply reuse the put_debt method since DynamoDB's put_item replaces the item if it exists
        return self.put_debt(debt)
