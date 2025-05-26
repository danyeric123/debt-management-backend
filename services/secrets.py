# Cost-effective secret management for personal projects
# Supports both environment variables (free) and AWS Secrets Manager (with rotation)

import boto3
from botocore.exceptions import ClientError


def get_secret(version_stage="AWSCURRENT"):
    """
    Get secret from AWS Secrets Manager.

    Args:
        version_stage: The version stage to retrieve (AWSCURRENT or AWSPREVIOUS)

    Returns:
        The secret string value
    """
    secret_name = "authSecrets"
    region_name = "us-east-1"

    # Create a Secrets Manager client
    session = boto3.session.Session()
    client = session.client(service_name="secretsmanager", region_name=region_name)

    try:
        get_secret_value_response = client.get_secret_value(
            SecretId=secret_name, VersionStage=version_stage
        )
    except ClientError as e:
        # For a list of exceptions thrown, see
        # https://docs.aws.amazon.com/secretsmanager/latest/apireference/API_GetSecretValue.html
        raise e

    # Decrypts secret using the associated KMS key.
    secret = get_secret_value_response["SecretString"]

    return secret


def get_all_secret_versions():
    """
    Get all available secret versions for JWT validation.
    Returns current and previous versions to handle rotation.
    """
    secrets = []

    # Get current version from Secrets Manager
    try:
        current = get_secret("AWSCURRENT")
        secrets.append(current)
    except ClientError:
        pass

    # Get previous version (for rotation support)
    try:
        previous = get_secret("AWSPREVIOUS")
        if previous and previous not in secrets:
            secrets.append(previous)
    except ClientError:
        pass

    return secrets
