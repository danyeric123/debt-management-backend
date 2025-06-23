"""
JWT Authorization Lambda for API Gateway.

This module provides JWT token validation for protected API endpoints.
It validates Supabase JWT tokens and verifies user existence in the database.
"""

from typing import Any, Dict, Optional

from services.dynamodb import dynamodb
from services.supabase_auth import supabase_auth
from utils.logging import log_error, setup_logger

# Initialize shared resources at module level for optimal Lambda performance
# This avoids re-initialization on warm starts and reduces cold start time
logger = setup_logger(__name__)


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    HTTP API Gateway Lambda Authorizer.

    Validates a Supabase JWT token and enriches the context with the user's
    internal profile, including the username. The authorizer response is cached
    by API Gateway for performance.

    Args:
        event: API Gateway authorizer event
        context: Lambda context object

    Returns:
        Authorization response for API Gateway
    """
    logger.info(
        "Authorization request received",
        extra={
            "request_id": getattr(context, "aws_request_id", "unknown"),
            "method": event.get("requestContext", {}).get("http", {}).get("method"),
            "path": event.get("rawPath"),
        },
    )

    try:
        # Extract and validate Supabase user from request token
        user_info = supabase_auth.get_user_from_request(event)
        if not user_info or not user_info.get("supabase_id"):
            logger.warning(
                "Authorization failed: No valid Supabase user found in token."
            )
            return {"isAuthorized": False}

        # Get user from DynamoDB by Supabase ID to ensure they are synced
        user = dynamodb.get_user_by_supabase_id(user_info["supabase_id"])
        if not user:
            logger.warning(
                "User not found in DynamoDB, denying access.",
                extra={"supabase_id": user_info["supabase_id"]},
            )
            return {"isAuthorized": False}

        username = user.get("username")
        if not username:
            logger.error(
                "User found in DB but has no username.",
                extra={"supabase_id": user_info["supabase_id"]},
            )
            return {"isAuthorized": False}

        logger.info(
            "User authorized successfully",
            extra={
                "username": username,
                "supabase_id": user_info["supabase_id"],
            },
        )

        # Return authorization success with enriched context
        return {
            "isAuthorized": True,
            "context": {
                "principalId": username,
                "username": username,
                "supabase_id": user_info["supabase_id"],
                "email": user.get("email"),
            },
        }

    except Exception as e:
        log_error(
            logger,
            e,
            {
                "event_path": event.get("rawPath"),
                "event_method": event.get("requestContext", {})
                .get("http", {})
                .get("method"),
            },
        )
        return {"isAuthorized": False}
