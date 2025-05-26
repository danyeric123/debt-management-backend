#!/usr/bin/env python3
"""
Standalone script to generate content-based image tags for Docker Lambda deployments.
This ensures consistent tagging between Pulumi infrastructure and Makefile builds.
"""

import hashlib
import os
from datetime import datetime


def get_content_hash():
    """Generate a hash based on the content of the source code."""
    hash_md5 = hashlib.md5()

    # Include key files that affect the Docker image
    files_to_hash = [
        "../Dockerfile",
        "../pyproject.toml",
        "../uv.lock",
        "../main.py",
        "../authorizer.py",
    ]

    # Add all Python files in handlers, models, services, utils
    for root in ["../handlers", "../models", "../services", "../utils"]:
        if os.path.exists(root):
            for subdir, dirs, files in os.walk(root):
                for file in files:
                    if file.endswith(".py"):
                        files_to_hash.append(os.path.join(subdir, file))

    # Hash the content of all files
    for file_path in files_to_hash:
        try:
            if os.path.exists(file_path):
                with open(file_path, "rb") as f:
                    hash_md5.update(f.read())
        except Exception:
            # If file doesn't exist or can't be read, skip it
            pass

    # Add current timestamp to ensure uniqueness even with same content
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    hash_md5.update(timestamp.encode())

    return f"{timestamp}-{hash_md5.hexdigest()[:8]}"


if __name__ == "__main__":
    print(get_content_hash())
