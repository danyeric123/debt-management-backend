# Multi-stage build for Lambda function using uv
FROM --platform=linux/amd64 ghcr.io/astral-sh/uv:0.7.8 AS uv

FROM --platform=linux/amd64 public.ecr.aws/lambda/python:3.13 AS builder

# Copy uv binary from the uv image
COPY --from=uv /uv /bin/uv

# Set environment variables for uv
ENV UV_COMPILE_BYTECODE=1
ENV UV_NO_INSTALLER_METADATA=1
ENV UV_LINK_MODE=copy

# Copy dependency files
COPY uv.lock pyproject.toml ./

# Install dependencies
RUN uv export --frozen --no-emit-workspace --no-dev --no-editable -o requirements.txt && \
    uv pip install -r requirements.txt --target "${LAMBDA_TASK_ROOT}"

# Final stage
FROM --platform=linux/amd64 public.ecr.aws/lambda/python:3.13

# Copy installed dependencies from builder stage
COPY --from=builder ${LAMBDA_TASK_ROOT} ${LAMBDA_TASK_ROOT}

# Copy application code
COPY . ${LAMBDA_TASK_ROOT}

# Set the CMD to your handler (this can be overridden by Lambda function configuration)
CMD ["main.healthz"] 