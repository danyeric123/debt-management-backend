#!/usr/bin/env python3
"""
Upload environment variables to AWS Parameter Store.

This script reads variables from a .env file and uploads them to AWS Parameter Store
with proper structure and encryption for sensitive values.
"""

import os
import sys
from pathlib import Path

import boto3
import click
from botocore.exceptions import ClientError
from dotenv import load_dotenv


def load_env_file(env_file_path: str = ".env") -> dict:
    """
    Load environment variables from .env file.

    Args:
        env_file_path: Path to .env file

    Returns:
        Dictionary of environment variables
    """
    if not Path(env_file_path).exists():
        click.secho(f"Error: {env_file_path} file not found", fg="red", err=True)
        sys.exit(1)

    # Load .env file
    load_dotenv(env_file_path)

    # Google OAuth parameters that should be uploaded
    oauth_params = {
        "oauth/google/client-id": os.getenv("GOOGLE_CLIENT_ID"),
        "oauth/google/client-secret": os.getenv("GOOGLE_CLIENT_SECRET"),
        "oauth/google/redirect-uri": os.getenv("GOOGLE_REDIRECT_URI"),
    }

    # Filter out None values
    oauth_params = {k: v for k, v in oauth_params.items() if v is not None}

    if not oauth_params:
        click.secho(
            "Warning: No Google OAuth parameters found in .env file", fg="yellow"
        )
        click.echo(
            "Expected variables: GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, GOOGLE_REDIRECT_URI"
        )

    return oauth_params


def upload_parameters(
    parameters: dict, parameter_prefix: str = "/debt-management", dry_run: bool = False
) -> None:
    """
    Upload parameters to AWS Parameter Store.

    Args:
        parameters: Dictionary of parameter names to values
        parameter_prefix: Prefix for parameter names
        dry_run: If True, only print what would be uploaded
    """
    if not parameters:
        click.secho("No parameters to upload", fg="yellow")
        return

    if dry_run:
        click.secho("DRY RUN - Would upload the following parameters:", fg="blue")
        for param_name, value in parameters.items():
            full_name = f"{parameter_prefix}/{param_name}"
            masked_value = value[:10] + "..." if len(value) > 10 else value
            click.echo(f"  {full_name} = {masked_value}")
        return

    ssm = boto3.client("ssm")

    with click.progressbar(parameters.items(), label="Uploading parameters") as items:
        for param_name, value in items:
            full_name = f"{parameter_prefix}/{param_name}"

            try:
                # Use SecureString for sensitive OAuth parameters
                parameter_type = (
                    "SecureString" if "secret" in param_name.lower() else "String"
                )

                response = ssm.put_parameter(
                    Name=full_name,
                    Value=value,
                    Type=parameter_type,
                    Description=f"Google OAuth parameter: {param_name}",
                    Overwrite=True,
                )

                click.secho(
                    f"✓ Uploaded {full_name} (version {response['Version']})",
                    fg="green",
                )

            except ClientError as e:
                click.secho(f"✗ Failed to upload {full_name}: {e}", fg="red", err=True)


def verify_parameters(
    parameters: dict, parameter_prefix: str = "/debt-management"
) -> None:
    """
    Verify that parameters were uploaded correctly.

    Args:
        parameters: Dictionary of parameter names to check
        parameter_prefix: Prefix for parameter names
    """
    click.secho("\nVerifying uploaded parameters...", fg="blue")
    ssm = boto3.client("ssm")

    for param_name in parameters.keys():
        full_name = f"{parameter_prefix}/{param_name}"

        try:
            response = ssm.get_parameter(Name=full_name, WithDecryption=True)
            click.secho(
                f"✓ {full_name} exists (version {response['Parameter']['Version']})",
                fg="green",
            )
        except ClientError as e:
            if e.response["Error"]["Code"] == "ParameterNotFound":
                click.secho(f"✗ {full_name} not found", fg="red")
            else:
                click.secho(f"✗ Error checking {full_name}: {e}", fg="red")


@click.command()
@click.option("--env-file", default=".env", help="Path to .env file", show_default=True)
@click.option(
    "--prefix",
    default="/debt-management",
    help="Parameter Store prefix",
    show_default=True,
)
@click.option(
    "--dry-run", is_flag=True, help="Show what would be uploaded without uploading"
)
@click.option("--verify", is_flag=True, help="Verify parameters after upload")
@click.option("--verbose", "-v", is_flag=True, help="Enable verbose output")
def main(env_file: str, prefix: str, dry_run: bool, verify: bool, verbose: bool):
    """
    Upload environment variables from .env file to AWS Parameter Store.

    This script securely uploads Google OAuth configuration to Parameter Store
    with proper encryption for sensitive values.
    """
    if verbose:
        click.secho(f"Loading environment variables from {env_file}", fg="blue")

    parameters = load_env_file(env_file)

    if not parameters:
        click.secho("No parameters found to upload", fg="red", err=True)
        sys.exit(1)

    click.secho(f"Found {len(parameters)} OAuth parameters", fg="green")

    if verbose:
        click.secho("Parameters to process:", fg="blue")
        for param_name in parameters.keys():
            click.echo(f"  - {param_name}")

    # Upload parameters
    upload_parameters(parameters, prefix, dry_run)

    # Verify if not dry run
    if not dry_run and verify:
        verify_parameters(parameters, prefix)

    if not dry_run:
        click.secho("\n✅ Parameter upload complete!", fg="green")
        click.echo(f"Parameters are now available at prefix: {prefix}")
        click.echo("\nYou can test the configuration with:")
        click.echo(
            'python -c "from services.parameter_store import config; print(config.load_oauth_config())"'
        )
    elif dry_run:
        click.secho(
            "\n🔍 Dry run complete. Use --verify flag to upload and verify.", fg="blue"
        )


if __name__ == "__main__":
    main()
