"""
Authentication handlers for the debt management API.

This module provides Supabase authentication integration,
handling user synchronization between Supabase Auth and DynamoDB.
"""

import json
import logging
from typing import Any, Dict

from models.users import UserBase
from services.dynamodb import dynamodb
from services.supabase_auth import supabase_auth
from utils.decorators import lambda_handler
from utils.responses import cors_headers, success_response

logger = logging.getLogger()
logger.setLevel(logging.INFO)


@lambda_handler()
def sync_user_handler(event: dict, context: dict) -> dict:
    """
    Sync a Supabase user with DynamoDB
    This is called when a user first authenticates or when user data needs to be synced
    """
    try:
        logger.info(f"Sync user request: {json.dumps(event, default=str)}")

        # Validate user from Supabase token
        user_info = supabase_auth.get_user_from_request(event)
        if not user_info:
            return {
                "statusCode": 401,
                "headers": cors_headers,
                "body": json.dumps({"error": "Unauthorized"}),
            }

        # FIRST: Check if user already exists by Supabase ID
        try:
            existing_user = dynamodb.get_user_by_supabase_id(user_info["supabase_id"])
            if existing_user:
                logger.info(f"User already exists: {existing_user['username']}")
                return {
                    "statusCode": 200,
                    "headers": cors_headers,
                    "body": json.dumps(
                        {
                            "username": existing_user["username"],
                            "email": existing_user["email"],
                            "full_name": existing_user["full_name"],
                            "supabase_id": existing_user["supabase_id"],
                            "avatar_url": existing_user.get("avatar_url"),
                            "created_at": existing_user["created_at"],
                        }
                    ),
                }
        except Exception as e:
            logger.info(f"User not found by Supabase ID, creating new: {str(e)}")

        # Parse request body for user data
        body = json.loads(event.get("body", "{}"))

        # ONLY NOW: Generate username from email if not provided (since we know user doesn't exist)
        username = body.get("username")
        if not username:
            username = (
                user_info["email"].split("@")[0].replace(".", "_").replace("-", "_")
            )
            # Ensure username is unique by checking DynamoDB once.
            # If it exists, append a part of the unique Supabase ID.
            try:
                existing_user = dynamodb.get_user_by_username(username)
                if existing_user:
                    unique_suffix = user_info["supabase_id"].split("-")[0]
                    username = f"{username}_{unique_suffix}"
            except Exception:
                pass  # Username is likely available

        # Create new user
        user_data = UserBase(
            username=username,
            email=user_info["email"],
            full_name=body.get(
                "full_name", user_info.get("user_metadata", {}).get("full_name", "")
            ),
            supabase_id=user_info["supabase_id"],
            avatar_url=user_info.get("user_metadata", {}).get("avatar_url"),
            is_email_verified=user_info.get("email_verified", True),
        )

        # Save to DynamoDB
        dynamodb.create_user(user_data)

        logger.info(f"Successfully created user: {username}")

        response_data = {
            "username": user_data.username,
            "email": user_data.email,
            "full_name": user_data.full_name,
            "supabase_id": user_data.supabase_id,
            "avatar_url": user_data.avatar_url,
            "created_at": (
                user_data.created_at.isoformat() if user_data.created_at else None
            ),
        }

        return success_response(data=response_data, status_code=201)

    except json.JSONDecodeError:
        return {
            "statusCode": 400,
            "headers": cors_headers,
            "body": json.dumps({"error": "Invalid JSON in request body"}),
        }
    except Exception as e:
        logger.error(f"Error syncing user: {str(e)}")
        return {
            "statusCode": 500,
            "headers": cors_headers,
            "body": json.dumps({"error": "Internal server error"}),
        }
