"""
Health check endpoint for the debt management API.

This module provides a simple health check endpoint that can be used
for monitoring and load balancer health checks.
"""

from utils.decorators import lambda_handler
from utils.responses import success_response


@lambda_handler()
def healthz(event, context):
    """
    Health check endpoint for the debt management API.

    Returns a simple success response to indicate the service is running.
    This endpoint does not require authentication and can be used by
    load balancers and monitoring systems.

    Args:
        event: Lambda event object
        context: Lambda context object

    Returns:
        HTTP response indicating service health
    """
    return success_response(
        data={
            "status": "healthy",
            "service": "debt-management-api",
            "version": "2.0.1",  # Testing content-based deployment
        },
        message="Service is running",
    )
