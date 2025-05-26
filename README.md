# Debt Management Backend

A serverless debt management API built with Python, deployed using Pulumi with Docker-based Lambda functions.

## Architecture

- **Lambda Functions**: Docker-based functions using uv for dependency management
- **DynamoDB**: Single table design with partition key (PK) and sort key (SK)
- **API Gateway**: HTTP API for RESTful endpoints
- **Secrets Manager**: Secure storage for authentication secrets
- **ECR**: Container registry for Lambda Docker images
- **CloudWatch**: Logging and monitoring

## Project Structure

```
debt-management-backend/
├── infrastructure/           # Pulumi infrastructure code
│   ├── components/          # Reusable Pulumi components
│   │   ├── __init__.py     # Components package
│   │   └── lambda_function.py # Docker Lambda function component
│   ├── __main__.py         # Main infrastructure definition
│   ├── Pulumi.yaml         # Pulumi project configuration
│   └── requirements.txt    # Infrastructure dependencies
├── handlers/               # Lambda function handlers
│   ├── __init__.py        # Handlers package
│   ├── auth.py            # Authentication endpoints
│   ├── users.py           # User management endpoints
│   └── debts.py           # Debt management endpoints
├── models/                 # Data models
│   ├── __init__.py        # Models package
│   ├── users.py           # User model
│   ├── debt.py            # Debt model
│   └── dynamodb.py        # DynamoDB item models
├── services/              # Service layer
│   ├── dynamodb.py        # DynamoDB operations
│   └── secrets.py         # Secrets Manager operations
├── utils/                 # Shared utilities
│   ├── __init__.py        # Utils package
│   ├── decorators.py      # Lambda handler decorators
│   ├── logging.py         # Centralized logging configuration
│   ├── responses.py       # Standardized HTTP responses
│   └── security.py        # Password hashing and security utilities
├── tests/                 # Test files and fixtures
│   └── fixtures/          # Test data files
├── backups/               # Infrastructure state backups
│   └── .gitkeep          # Preserve directory structure
├── authorizer.py          # JWT authorization Lambda
├── main.py               # Health check endpoint
├── Dockerfile            # Docker image definition using uv
├── Makefile             # Deployment and management commands
├── pyproject.toml       # Python project configuration
├── uv.lock             # Dependency lock file
└── README.md           # This file
```

## Prerequisites

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) for Python package management
- [Docker](https://www.docker.com/) for container builds
- [AWS CLI](https://aws.amazon.com/cli/) configured with appropriate permissions
- [Pulumi CLI](https://www.pulumi.com/docs/install/) (installed automatically by make install)

## Quick Start

1. **Install dependencies:**
   ```bash
   make install
   ```

2. **Login to AWS ECR:**
   ```bash
   make docker-login
   ```

3. **Preview infrastructure changes:**
   ```bash
   make preview
   ```

4. **Deploy the infrastructure:**
   ```bash
   make deploy
   ```

5. **Test the API:**
   ```bash
   make test
   ```

6. **Get the API URL:**
   ```bash
   make api-url
   ```

## Available Commands

| Command | Description |
|---------|-------------|
| `make help` | Show all available commands |
| `make install` | Install all dependencies |
| `make docker-login` | Login to AWS ECR |
| `make build-image` | Build Docker image locally |
| `make push-image` | Push Docker image to ECR |
| `make preview` | Preview infrastructure changes |
| `make deploy` | Full deploy (build, push image, deploy infrastructure) |
| `make deploy-infra` | Deploy infrastructure only (no image build) |
| `make update-image` | Build and push new image, update Lambda functions |
| `make destroy` | Destroy all infrastructure |
| `make test` | Test API endpoints |
| `make test-auth` | Test authorization flow specifically |
| `make logs FUNCTION=<name>` | View logs for a specific function |
| `make outputs` | Show all stack outputs |
| `make api-url` | Get the API endpoint URL |
| `make ecr-url` | Get the ECR repository URL |
| `make clean` | Clean up Docker resources |
| `make format` | Format code with ruff and isort |
| `make lint` | Lint code with ruff |
| `make build-local` | Build Docker image locally |
| `make run-local` | Run container locally for testing |

## API Endpoints

### Public Endpoints (No Authentication Required)
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/healthz` | Health check |
| POST | `/login` | Login and get JWT token |
| POST | `/users` | Create a new user account |

### Protected Endpoints (Authentication Required)
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/users/{username}` | Get user information |
| POST | `/debts` | Create a new debt |
| GET | `/debts` | List all debts for authenticated user |
| GET | `/debts/{debt_id}` | Get specific debt by ID |
| PUT | `/debts/{debt_id}` | Update a debt |
| DELETE | `/debts/{debt_id}` | Delete a debt |

### API Design Principles

This API follows modern REST best practices:

- **Flat URL Structure**: Uses `/debts/{debt_id}` instead of nested `/users/{username}/debts/{debt_name}`
- **UUID-Based Identification**: Debts are identified by auto-generated UUIDs, not user-provided names
- **Resource-Oriented**: Each endpoint represents a clear resource operation
- **Security Through Context**: User authorization is handled through JWT tokens, not URL parameters
- **URL-Safe Identifiers**: UUIDs avoid issues with special characters, spaces, and encoding

## Authentication

The API uses JWT (JSON Web Tokens) for authentication:

1. **Login**: POST to `/login` with username and password to get a JWT token
2. **Protected Endpoints**: Include the token in the `Authorization` header as `Bearer <token>`
3. **Token Expiration**: Tokens expire after 24 hours

### Example Authentication Flow

```bash
# 1. Create a user (no auth required)
curl -X POST https://your-api.com/users \
  -H "Content-Type: application/json" \
  -d '{"username":"john","email":"john@example.com","full_name":"John Doe","password":"securepass123"}'

# 2. Login to get a token
TOKEN=$(curl -X POST https://your-api.com/login \
  -H "Content-Type: application/json" \
  -d '{"username":"john","password":"securepass123"}' | jq -r '.token')

# 3. Use the token to access protected endpoints
curl https://your-api.com/users/john \
  -H "Authorization: Bearer $TOKEN"

# 4. Create a debt (returns debt with auto-generated UUID)
DEBT_RESPONSE=$(curl -X POST https://your-api.com/debts \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "debt_name": "Chase Credit Card",
    "principal": 5000.00,
    "interest_rate": 18.99,
    "start_date": "2024-01-01T00:00:00Z",
    "payment_frequency": "monthly",
    "current_balance": 4500.00,
    "creditor": "Chase Bank"
  }')

# 5. Extract debt_id from response and use it for operations
DEBT_ID=$(echo $DEBT_RESPONSE | jq -r '.data.debt_id')

# 6. Get specific debt by ID
curl https://your-api.com/debts/$DEBT_ID \
  -H "Authorization: Bearer $TOKEN"

# 7. List all debts for the user
curl https://your-api.com/debts \
  -H "Authorization: Bearer $TOKEN"
```

## Docker-based Lambda Functions

This project uses Docker containers for Lambda functions with **content-based image tagging** for automatic updates:

- **Automatic Updates**: Lambda functions update automatically when code changes
- **Content-Based Tagging**: Image tags based on source code content ensure reliable deployments
- **Consistent Environment**: Same runtime environment across development and production
- **Optimized Dependencies**: Uses uv for fast, deterministic dependency resolution
- **Better Cold Start**: Bytecode compilation enabled for improved performance
- **Larger Package Size**: Support for larger dependencies that exceed Lambda's zip limits

### Docker Image Features

- Based on `public.ecr.aws/lambda/python:3.13`
- Uses `ghcr.io/astral-sh/uv:0.7.8` for dependency management
- Bytecode compilation enabled (`UV_COMPILE_BYTECODE=1`)
- Optimized layer caching for faster builds
- Deterministic builds with locked dependencies
- **Content-based tagging**: Automatic Lambda updates when code changes

> 📖 **For detailed information about our deployment approach, see [DEPLOYMENT_BEST_PRACTICES.md](DEPLOYMENT_BEST_PRACTICES.md)**

## Infrastructure Components

### DockerLambdaFunction Component

A reusable Pulumi component that creates:
- ECR repository for the Docker image
- Automatic image building and pushing
- Lambda function with container image
- CloudWatch log group
- IAM role with necessary permissions
- Custom IAM policies for DynamoDB and Secrets Manager

### DynamoDB Table Design

Single table design with:
- **PK (Partition Key)**: `USER#{username}` or entity identifier
- **SK (Sort Key)**: `USER#INFO` for user records, `DEBT#{debt_name}` for debt records
- **GSI**: `SK-PK-index` for reverse lookups

## Environment Variables

Lambda functions receive these environment variables:
- `TABLE_NAME`: DynamoDB table name

## Secrets Management

The application uses AWS Secrets Manager for:
- JWT signing secrets (secret name: `authSecrets`)

## Development Workflow

### Initial Setup
1. **Install dependencies**: `make install`
2. **Login to ECR**: `make docker-login`
3. **Deploy infrastructure**: `make deploy`

### Code Changes
1. **Make code changes** to handlers, models, or services
2. **Test locally** (optional):
   ```bash
   make build-local
   make run-local
   ```
3. **Update image and functions** (faster than full deploy):
   ```bash
   make update-image
   ```
4. **Test the deployed API**:
   ```bash
   make test
   ```
5. **View logs** if needed:
   ```bash
   make logs FUNCTION=healthz
   ```

### Infrastructure Changes
1. **Preview changes**: `make preview`
2. **Deploy infrastructure only**: `make deploy-infra`
3. **Full deploy** (if both code and infrastructure changed): `make deploy`

## Migration from Serverless Framework

This project was migrated from Serverless Framework to Pulumi. Key differences:

### Advantages of Pulumi + Docker:
- **Real Python**: Full Python language features for infrastructure
- **Type Safety**: IDE support with autocomplete and type checking
- **Reusable Components**: Create and share infrastructure patterns
- **Container Benefits**: Larger packages, consistent environments
- **Better Dependency Management**: uv for fast, reliable builds

### Migration Steps:
1. Infrastructure defined in `infrastructure/__main__.py` (replaces `serverless.yaml`)
2. Docker-based deployment (replaces zip packaging)
3. Pulumi state management (replaces CloudFormation)
4. Make-based workflow (replaces `sls` commands)

## Monitoring and Debugging

### View Logs
```bash
# View logs for a specific function
make logs FUNCTION=healthz

# View logs in AWS Console
aws logs tail "/aws/lambda/debt-management-healthz" --follow
```

### Debug Locally
```bash
# Build and run container locally
make run-local

# Test with curl
curl -X POST http://localhost:9000/2015-03-31/functions/function/invocations \
  -d '{"httpMethod": "GET", "path": "/healthz"}'
```

## Code Organization & Patterns

This project follows a **modular monolith architecture** as recommended by modern Node.js best practices, adapted for Python serverless applications. The structure emphasizes domain responsibility over technical responsibility, making it easier to scale and maintain.

### Domain-Based Organization

Following the principles outlined in [The T-Shaped Dev's modular monolith approach](https://thetshaped.dev/p/how-to-better-structure-your-nodejs-project-modular-monolith), our project is organized by business domains rather than technical layers:

```
debt-management-backend/
├── handlers/          # API endpoints (domain controllers)
├── models/           # Data models and validation (domain entities)
├── services/         # Business logic and external integrations
├── utils/            # Shared utilities and cross-cutting concerns
└── infrastructure/   # Infrastructure as code
```

This structure provides:
- **Scalability**: Each domain can evolve independently
- **Maintainability**: Related code is co-located
- **Clarity**: The structure reflects business operations
- **Migration Path**: Easy transition to microservices if needed

### Standardized Handler Patterns

All Lambda handlers follow consistent patterns using decorators, inspired by modern web framework patterns:

```python
from utils.decorators import lambda_handler, validate_json_body, require_auth, extract_path_params
from utils.responses import success_response, error_response, HTTPStatus

@lambda_handler()  # Provides logging, error handling, timing
@require_auth      # Validates JWT token (for protected endpoints)
@validate_json_body(required_fields=["field1", "field2"])  # Validates request body
@extract_path_params("param1", "param2")  # Extracts path parameters
def my_handler(event, context):
    # Handler logic here
    return success_response(data={"result": "success"})
```

### Centralized Utilities

Following the DRY principle and centralized configuration patterns:

- **`utils/logging.py`**: Structured JSON logging for CloudWatch with consistent formatting
- **`utils/responses.py`**: Standardized HTTP response formatting with proper status codes
- **`utils/security.py`**: Secure password hashing with PBKDF2 (industry standard)
- **`utils/decorators.py`**: Reusable handler decorators for cross-cutting concerns

### Security Best Practices

Implementing security-first design principles:

- **Password Hashing**: PBKDF2 with SHA-256, 100,000 iterations, random salt generation
- **JWT Tokens**: Secure secret rotation support via AWS Secrets Manager
- **Input Validation**: Pydantic models with automatic validation and type checking
- **Error Handling**: Consistent error responses without information leakage
- **Logging**: Structured logging with request tracing and correlation IDs
- **Authorization**: Fine-grained access control (users can only access their own data)

### Infrastructure Patterns

Reusable infrastructure components following infrastructure as code best practices:

- **Reusable Components**: `DockerLambdaFunction` component for consistent Lambda setup
- **Shared Resources**: Single ECR repository for all Lambda functions (cost optimization)
- **Environment Variables**: Centralized configuration management
- **IAM Policies**: Least privilege principle with specific resource access
- **Monitoring**: CloudWatch integration with structured logging

## Security

- IAM roles follow least privilege principle
- Secure password hashing with PBKDF2 (100,000 iterations)
- JWT tokens with secret rotation support
- Secrets stored in AWS Secrets Manager
- API Gateway with CORS configuration
- CloudWatch logging for audit trails
- Input validation with Pydantic models

## Cost Optimization

- Pay-per-request DynamoDB billing
- Lambda functions scale to zero when not in use
- ECR repositories with lifecycle policies (can be added)
- CloudWatch log retention set to 14 days

## Troubleshooting

### Common Issues

1. **Docker build fails**: Ensure Docker is running and you have sufficient disk space
2. **Pulumi deployment fails**: Check AWS credentials and permissions
3. **Lambda timeout**: Increase timeout in the component configuration
4. **Image too large**: Optimize dependencies or use Lambda layers

### Getting Help

1. Check the logs: `make logs FUNCTION=<function-name>`
2. Verify stack outputs: `make outputs`
3. Test locally: `make run-local`
4. Check AWS Console for detailed error messages
