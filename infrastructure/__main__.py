import json
import os
import subprocess
import sys
from datetime import datetime

import pulumi
import pulumi_aws as aws
from components.lambda_function import DockerLambdaFunction

# Get current AWS account ID and region
current = aws.get_caller_identity()
current_region = aws.get_region()

# Shared ECR Repository for all Lambda functions
ecr_repository = aws.ecr.Repository(
    "debt-management-repo", name="debt-management-backend", force_delete=True
)


def get_content_hash():
    """Get content-based hash using the standalone script."""
    try:
        result = subprocess.run(
            [sys.executable, "get_image_tag.py"],
            capture_output=True,
            text=True,
            cwd=os.path.dirname(__file__),
        )
        if result.returncode == 0:
            return result.stdout.strip()
        else:
            # Fallback to timestamp if script fails
            return datetime.now().strftime("%Y%m%d-%H%M%S")
    except Exception:
        # Fallback to timestamp if script fails
        return datetime.now().strftime("%Y%m%d-%H%M%S")


# Use content-based image tag to force updates when code changes
# Read the tag from a file if it exists (set by Makefile), otherwise generate it
tag_file = "image_tag.txt"
if os.path.exists(tag_file):
    with open(tag_file, "r") as f:
        image_tag = f.read().strip()
else:
    image_tag = get_content_hash()

image_uri = ecr_repository.repository_url.apply(lambda url: f"{url}:{image_tag}")

# DynamoDB Table
dynamodb_table = aws.dynamodb.Table(
    "debt-management-table",
    name="DebtManagementTable",
    billing_mode="PAY_PER_REQUEST",
    attributes=[
        {"name": "PK", "type": "S"},
        {"name": "SK", "type": "S"},
    ],
    hash_key="PK",
    range_key="SK",
    global_secondary_indexes=[
        {
            "name": "SK-PK-index",
            "hash_key": "SK",
            "range_key": "PK",
            "projection_type": "ALL",
        }
    ],
)

# IAM Policies
dynamodb_policy = dynamodb_table.arn.apply(
    lambda arn: json.dumps(
        {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Action": [
                        "dynamodb:PutItem",
                        "dynamodb:GetItem",
                        "dynamodb:UpdateItem",
                        "dynamodb:DeleteItem",
                        "dynamodb:Query",
                        "dynamodb:Scan",
                    ],
                    "Resource": [arn, f"{arn}/index/*"],
                }
            ],
        }
    )
)

# Use existing AWS Secrets Manager Secret for JWT
# The secret "authSecrets" already exists and is managed externally
secrets_policy = pulumi.Output.concat(
    "arn:aws:secretsmanager:",
    current_region.name,
    ":",
    current.account_id,
    ":secret:authSecrets-*",
).apply(
    lambda arn: json.dumps(
        {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Action": [
                        "secretsmanager:GetSecretValue",
                        "secretsmanager:DescribeSecret",
                    ],
                    "Resource": arn,
                }
            ],
        }
    )
)

# Environment variables for Lambda functions
lambda_env_vars = {
    "TABLE_NAME": dynamodb_table.name,
    # JWT_SECRET removed - using AWS Secrets Manager for security
}

# Lambda Function Definitions
lambda_functions = {
    "healthz": {
        "handler": "main.healthz",
        "protected": False,  # No auth required
    },
    "login": {
        "handler": "handlers.auth.login",
        "protected": False,  # No auth required for login
    },
    "create-user": {
        "handler": "handlers.users.create_user",
        "protected": False,  # No auth required for user registration
    },
    "get-user": {
        "handler": "handlers.users.get_user",
        "protected": True,
    },
    "create-debt": {
        "handler": "handlers.debts.create_debt",
        "protected": True,
    },
    "get-debt": {
        "handler": "handlers.debts.get_debt",
        "protected": True,
    },
    "list-debts": {
        "handler": "handlers.debts.list_debts",
        "protected": True,
    },
    "update-debt": {
        "handler": "handlers.debts.update_debt",
        "protected": True,
    },
    "delete-debt": {
        "handler": "handlers.debts.delete_debt",
        "protected": True,
    },
}

# Create Lambda functions
functions = {}
for name, config in lambda_functions.items():
    functions[name] = DockerLambdaFunction(
        f"debt-management-{name}",
        handler=config["handler"],
        shared_image_uri=image_uri,
        environment_vars=lambda_env_vars,
        additional_policies=[dynamodb_policy, secrets_policy],
    )

# Create the authorizer function
authorizer_function = DockerLambdaFunction(
    "debt-management-authorizer",
    handler="authorizer.lambda_handler",
    shared_image_uri=image_uri,
    environment_vars=lambda_env_vars,
    additional_policies=[dynamodb_policy, secrets_policy],
)

# API Gateway HTTP API
api = aws.apigatewayv2.Api(
    "debt-management-api",
    protocol_type="HTTP",
    cors_configuration={
        "allow_origins": ["*"],
        "allow_headers": ["*"],
        "allow_methods": ["*"],
    },
)

# Lambda Authorizer for HTTP API Gateway
authorizer = aws.apigatewayv2.Authorizer(
    "lambda-authorizer",
    api_id=api.id,
    authorizer_type="REQUEST",
    authorizer_uri=authorizer_function.invoke_arn,
    authorizer_payload_format_version="2.0",
    identity_sources=["$request.header.Authorization"],
    name="lambda-authorizer",
    authorizer_result_ttl_in_seconds=300,  # Cache for 5 minutes
    enable_simple_responses=True,  # Use simple response format {"isAuthorized": true/false}
)

# Permission for API Gateway to invoke the authorizer
authorizer_permission = aws.lambda_.Permission(
    "authorizer-permission",
    action="lambda:InvokeFunction",
    function=authorizer_function.name,
    principal="apigateway.amazonaws.com",
    source_arn=pulumi.Output.concat(api.execution_arn, "/authorizers/", authorizer.id),
)

# API Gateway Stage with logging
stage = aws.apigatewayv2.Stage(
    "debt-management-stage",
    api_id=api.id,
    name="dev",
    auto_deploy=True,
    access_log_settings={
        "destination_arn": pulumi.Output.concat(
            "arn:aws:logs:",
            current_region.name,
            ":",
            current.account_id,
            ":log-group:/aws/apigateway/debt-management-api",
        ),
        "format": "$context.requestId $context.status $context.error.message $context.error.messageString $context.integrationErrorMessage",
    },
)

# Route Definitions
routes = [
    {"method": "GET", "path": "/healthz", "function": "healthz", "protected": False},
    {"method": "POST", "path": "/login", "function": "login", "protected": False},
    {"method": "POST", "path": "/users", "function": "create-user", "protected": False},
    {
        "method": "GET",
        "path": "/users/{username}",
        "function": "get-user",
        "protected": True,
    },
    # New REST API design for debts - flat structure with UUID identification
    {
        "method": "POST",
        "path": "/debts",
        "function": "create-debt",
        "protected": True,
    },
    {
        "method": "GET",
        "path": "/debts",
        "function": "list-debts",
        "protected": True,
    },
    {
        "method": "GET",
        "path": "/debts/{debt_id}",
        "function": "get-debt",
        "protected": True,
    },
    {
        "method": "PUT",
        "path": "/debts/{debt_id}",
        "function": "update-debt",
        "protected": True,
    },
    {
        "method": "DELETE",
        "path": "/debts/{debt_id}",
        "function": "delete-debt",
        "protected": True,
    },
]

# Create integrations, permissions, and routes
for route_config in routes:
    function_name = route_config["function"]
    route_key = f"{route_config['method']} {route_config['path']}"
    resource_name = function_name.replace("-", "_")

    # Lambda Permission - use wildcard for path parameters
    permission = aws.lambda_.Permission(
        f"{resource_name}-permission",
        action="lambda:InvokeFunction",
        function=functions[function_name].name,
        principal="apigateway.amazonaws.com",
        source_arn=pulumi.Output.concat(
            api.execution_arn,
            "/",
            stage.name,
            "/",
            route_config["method"],
            "/*",  # Use wildcard to handle path parameters
        ),
    )

    # Integration
    integration = aws.apigatewayv2.Integration(
        f"{resource_name}-integration",
        api_id=api.id,
        integration_type="AWS_PROXY",
        integration_uri=functions[function_name].invoke_arn,
        integration_method="POST",
        payload_format_version="2.0",
    )

    # Route (with or without authorizer)
    route_args = {
        "api_id": api.id,
        "route_key": route_key,
        "target": pulumi.Output.concat("integrations/", integration.id),
    }

    # Add authorizer for protected routes
    if route_config["protected"]:
        route_args["authorization_type"] = "CUSTOM"
        route_args["authorizer_id"] = authorizer.id

    route = aws.apigatewayv2.Route(f"{resource_name}-route", **route_args)

# Exports
pulumi.export("ecr_repository_url", ecr_repository.repository_url)
pulumi.export("image_tag", image_tag)
pulumi.export("image_uri", image_uri)
pulumi.export(
    "api_url",
    pulumi.Output.concat(
        "https://",
        api.id,
        ".execute-api.",
        current_region.name,
        ".amazonaws.com/",
        stage.name,
    ),
)
pulumi.export("api_id", api.id)
pulumi.export("authorizer_id", authorizer.id)
pulumi.export("dynamodb_table_name", dynamodb_table.name)
pulumi.export("dynamodb_table_arn", dynamodb_table.arn)
