"""
Debt management handlers for the debt management API.

This module provides CRUD operations for debt management following REST best practices:
- Flat URL structure: /debts/{debt_id} instead of nested /users/{username}/debts/{debt_name}
- UUID-based identification for stable, URL-safe identifiers
- Proper HTTP methods and status codes
- User authorization through JWT context
"""

import logging
from datetime import datetime, timezone

from pydantic import ValidationError

from models.debt import DebtBase, DebtCreate, debt_item_to_dict
from services.dynamodb import DebtManagementTable
from utils.decorators import (extract_path_params, lambda_handler,
                              require_auth, validate_json_body)
from utils.responses import (HTTPStatus, error_response, not_found_response,
                             success_response, validation_error_response)

# Initialize shared resources at module level for optimal Lambda performance
# This avoids re-initialization on warm starts and reduces cold start time
logger = logging.getLogger(__name__)
table = DebtManagementTable()


@lambda_handler()
@require_auth
@validate_json_body()
def create_debt(event, context):
    """
    Create a new debt for the authenticated user.

    POST /debts

    Creates a debt with auto-generated UUID. The username is taken from the JWT token,
    ensuring users can only create debts for themselves.

    Args:
        event: Lambda event object containing debt data
        context: Lambda context object

    Returns:
        HTTP response with created debt data including the generated debt_id
    """
    body = event["json_body"]
    auth_username = event["auth"]["username"]

    try:
        # Validate the input using DebtCreate model
        debt_create = DebtCreate(**body)

        # Add username from auth context and create full debt model
        debt_data = debt_create.model_dump()
        debt_data["username"] = auth_username

        # Create and validate debt model (debt_id will be auto-generated)
        debt = DebtBase(**debt_data)

        # Add timestamps
        now = datetime.now(timezone.utc)
        debt.created_at = now
        debt.updated_at = now

        # Use shared table instance for optimal performance
        table.put_debt(debt)

        return success_response(
            data=debt_item_to_dict(debt.to_dynamodb_item()),
            message=f"Debt '{debt.debt_name}' created successfully",
            status_code=HTTPStatus.CREATED,
        )

    except ValidationError as e:
        return validation_error_response(
            "Debt validation failed", {"validation_errors": e.errors()}
        )
    except Exception as e:
        # Log the actual exception for debugging
        logger.error(f"Error creating debt: {str(e)}", exc_info=True)

        # Check for common database errors
        error_str = str(e).lower()
        if "already exists" in error_str or "duplicate" in error_str:
            return error_response(
                f"Debt with ID {body.get('debt_id', 'unknown')} already exists",
                HTTPStatus.CONFLICT,
            )

        # Return the actual error message for debugging (in production, you might want to be more generic)
        return error_response(
            f"Failed to create debt: {str(e)}", HTTPStatus.INTERNAL_SERVER_ERROR
        )


@lambda_handler()
@require_auth
@extract_path_params("debt_id")
def get_debt(event, context):
    """
    Get a specific debt by ID.

    GET /debts/{debt_id}

    Retrieves debt data for the specified debt ID. Users can only access their own debts.

    Args:
        event: Lambda event object with debt_id path parameter
        context: Lambda context object

    Returns:
        HTTP response with debt data or error message
    """
    debt_id = event["path_params"]["debt_id"]
    auth_username = event["auth"]["username"]

    # Use shared table instance for optimal performance
    debt = table.get_debt(auth_username, debt_id)

    if not debt:
        return not_found_response("Debt", debt_id)

    # Verify ownership (additional security check)
    if debt.username != auth_username:
        return error_response(
            "Access denied: You can only access your own debts",
            HTTPStatus.FORBIDDEN,
        )

    return success_response(data=debt_item_to_dict(debt.to_dynamodb_item()))


@lambda_handler()
@require_auth
def list_debts(event, context):
    """
    List all debts for the authenticated user.

    GET /debts

    Retrieves all debts for the authenticated user. Supports optional query parameters
    for filtering and pagination (can be added later).

    Args:
        event: Lambda event object
        context: Lambda context object

    Returns:
        HTTP response with list of debts
    """
    auth_username = event["auth"]["username"]

    try:
        # Use shared table instance for optimal performance
        debts = table.list_user_debts(auth_username)

        # Calculate summary statistics
        total_principal = sum(debt.principal for debt in debts)
        total_balance = sum(debt.current_balance or 0 for debt in debts)

        return success_response(
            data={
                "debts": [debt_item_to_dict(debt.to_dynamodb_item()) for debt in debts],
                "summary": {
                    "total_debts": len(debts),
                    "total_principal": float(total_principal),
                    "total_current_balance": float(total_balance),
                },
            }
        )
    except Exception as e:
        # Log the actual exception for debugging
        logger.error(
            f"Error listing debts for user {auth_username}: {str(e)}", exc_info=True
        )

        return error_response(
            f"Failed to list debts: {str(e)}", HTTPStatus.INTERNAL_SERVER_ERROR
        )


@lambda_handler()
@require_auth
@validate_json_body()
@extract_path_params("debt_id")
def update_debt(event, context):
    """
    Update an existing debt.

    PUT /debts/{debt_id}

    Updates debt data while preserving debt_id and created_at timestamp.
    Users can only update their own debts.

    Args:
        event: Lambda event object containing updated debt data
        context: Lambda context object

    Returns:
        HTTP response with success message or error
    """
    body = event["json_body"]
    debt_id = event["path_params"]["debt_id"]
    auth_username = event["auth"]["username"]

    # Get existing debt using shared table instance
    existing_debt = table.get_debt(auth_username, debt_id)
    if not existing_debt:
        return not_found_response("Debt", debt_id)

    # Verify ownership
    if existing_debt.username != auth_username:
        return error_response(
            "Access denied: You can only update your own debts",
            HTTPStatus.FORBIDDEN,
        )

    try:
        # Create a copy of existing debt data
        updated_data = existing_debt.model_dump()

        # Update only the fields provided in the request
        for field, value in body.items():
            if value is not None:  # Only update non-null values
                updated_data[field] = value

        # Ensure required fields are preserved
        updated_data["username"] = auth_username
        updated_data["debt_id"] = debt_id
        updated_data["created_at"] = existing_debt.created_at
        updated_data["updated_at"] = datetime.now(timezone.utc)

        # Create updated debt model
        updated_debt = DebtBase(**updated_data)

        # Store updated debt using shared table instance
        table.update_debt(updated_debt)

        return success_response(
            data=debt_item_to_dict(updated_debt.to_dynamodb_item()),
            message=f"Debt '{updated_debt.debt_name}' updated successfully",
        )

    except ValidationError as e:
        return validation_error_response(
            "Debt validation failed", {"validation_errors": e.errors()}
        )
    except Exception:
        return error_response("Failed to update debt", HTTPStatus.INTERNAL_SERVER_ERROR)


@lambda_handler()
@require_auth
@extract_path_params("debt_id")
def delete_debt(event, context):
    """
    Delete a debt.

    DELETE /debts/{debt_id}

    Removes the specified debt from the database. Users can only delete their own debts.

    Args:
        event: Lambda event object with debt_id path parameter
        context: Lambda context object

    Returns:
        HTTP response with success message or error
    """
    debt_id = event["path_params"]["debt_id"]
    auth_username = event["auth"]["username"]

    # Check if debt exists and verify ownership using shared table instance
    existing_debt = table.get_debt(auth_username, debt_id)
    if not existing_debt:
        return not_found_response("Debt", debt_id)

    if existing_debt.username != auth_username:
        return error_response(
            "Access denied: You can only delete your own debts",
            HTTPStatus.FORBIDDEN,
        )

    try:
        # Delete debt using shared table instance
        table.delete_debt(auth_username, debt_id)

        return success_response(
            data={
                "debt_id": debt_id,
                "debt_name": existing_debt.debt_name,
                "username": auth_username,
            },
            message=f"Debt '{existing_debt.debt_name}' deleted successfully",
        )

    except Exception:
        return error_response("Failed to delete debt", HTTPStatus.INTERNAL_SERVER_ERROR)
