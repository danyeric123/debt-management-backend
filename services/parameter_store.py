"""
AWS Systems Manager Parameter Store service.

This module provides secure parameter retrieval from AWS Parameter Store
with local development support using .env files and python-dotenv.
"""

import os
from functools import lru_cache
from typing import Any, Dict

import boto3
from botocore.exceptions import ClientError
from dotenv import load_dotenv

from utils.logging import setup_logger

logger = setup_logger(__name__)

# Load .env file for local development
load_dotenv()

# Cache for Parameter Store client
_ssm_client = None


def get_ssm_client():
    """Get or create SSM client with caching."""
    global _ssm_client
    if _ssm_client is None:
        _ssm_client = boto3.client("ssm")
    return _ssm_client


@lru_cache(maxsize=128)
def get_parameter(parameter_name: str, decrypt: bool = True) -> str | None:
    """
    Get a parameter from AWS Parameter Store with caching.

    Falls back to environment variables for local development.

    Args:
        parameter_name: The name of the parameter to retrieve
        decrypt: Whether to decrypt SecureString parameters

    Returns:
        Parameter value or None if not found
    """
    # For local development, check environment variables first
    env_var = parameter_name.replace("/", "_").replace("-", "_").upper()
    local_value = os.getenv(env_var)

    if local_value:
        logger.debug(f"Using local environment variable for {parameter_name}")
        return local_value

    # Try to get from Parameter Store
    try:
        ssm = get_ssm_client()
        response = ssm.get_parameter(Name=parameter_name, WithDecryption=decrypt)
        value = response["Parameter"]["Value"]

        logger.debug(f"Retrieved parameter {parameter_name} from Parameter Store")
        return value

    except ClientError as e:
        error_code = e.response["Error"]["Code"]

        if error_code == "ParameterNotFound":
            logger.warning(f"Parameter {parameter_name} not found in Parameter Store")
        else:
            logger.error(f"Error retrieving parameter {parameter_name}: {e}")

        return None
    except Exception as e:
        logger.error(f"Unexpected error retrieving parameter {parameter_name}: {e}")
        return None


@lru_cache(maxsize=32)
def get_parameters_by_path(path: str, decrypt: bool = True) -> Dict[str, str]:
    """
    Get multiple parameters by path prefix with caching.

    Args:
        path: The path prefix to search for parameters
        decrypt: Whether to decrypt SecureString parameters

    Returns:
        Dictionary of parameter names (without path) to values
    """
    try:
        ssm = get_ssm_client()

        parameters = {}
        paginator = ssm.get_paginator("get_parameters_by_path")

        for page in paginator.paginate(
            Path=path, Recursive=True, WithDecryption=decrypt
        ):
            for param in page["Parameters"]:
                # Remove path prefix from name
                param_name = param["Name"].replace(path, "").lstrip("/")
                parameters[param_name] = param["Value"]

        logger.debug(f"Retrieved {len(parameters)} parameters from path {path}")
        return parameters

    except ClientError as e:
        logger.error(f"Error retrieving parameters by path {path}: {e}")
        return {}
    except Exception as e:
        logger.error(f"Unexpected error retrieving parameters by path {path}: {e}")
        return {}


class ParameterStoreConfig:
    """
    Configuration class that loads parameters from Parameter Store or environment.

    Provides a clean interface for accessing configuration values with automatic
    fallback and caching.
    """

    def __init__(self, parameter_prefix: str = "/debt-management"):
        """
        Initialize configuration with parameter prefix.

        Args:
            parameter_prefix: Prefix for parameter names in Parameter Store
        """
        self.parameter_prefix = parameter_prefix.rstrip("/")
        self._config_cache = {}

    def get(self, key: str, default: Any = None) -> Any:
        """
        Get a configuration value.

        Args:
            key: Configuration key (will be prefixed with parameter_prefix)
            default: Default value if not found

        Returns:
            Configuration value or default
        """
        if key in self._config_cache:
            return self._config_cache[key]

        parameter_name = f"{self.parameter_prefix}/{key}"
        value = get_parameter(parameter_name)

        if value is None:
            value = default

        self._config_cache[key] = value
        return value

    def get_required(self, key: str) -> str:
        """
        Get a required configuration value.

        Args:
            key: Configuration key

        Returns:
            Configuration value

        Raises:
            ValueError: If parameter is not found
        """
        value = self.get(key)
        if value is None:
            raise ValueError(
                f"Required parameter {self.parameter_prefix}/{key} not found"
            )
        return value

    def load_oauth_config(self) -> Dict[str, str]:
        """
        Load Google OAuth configuration parameters.

        Returns:
            Dictionary with OAuth configuration

        Raises:
            ValueError: If required OAuth parameters are missing
        """
        config = {
            "client_id": self.get_required("oauth/google/client-id"),
            "client_secret": self.get_required("oauth/google/client-secret"),
            "redirect_uri": self.get_required("oauth/google/redirect-uri"),
        }

        logger.info("Loaded Google OAuth configuration from Parameter Store")
        return config


# Global config instance
config = ParameterStoreConfig()


def clear_cache():
    """Clear parameter cache. Useful for testing or config updates."""
    get_parameter.cache_clear()
    get_parameters_by_path.cache_clear()
    config._config_cache.clear()
    logger.info("Parameter Store cache cleared")
