.PHONY: help install preview deploy destroy clean logs test docker-login build-image push-image

# Default target
help:
	@echo "Available commands:"
	@echo "  install       - Install dependencies and set up environment"
	@echo "  start-docker  - Start Docker daemon"
	@echo "  check-docker  - Check if Docker is running"
	@echo "  docker-login  - Login to AWS ECR"
	@echo "  build-image   - Build Docker image locally"
	@echo "  push-image    - Push Docker image to ECR with content-based tag"
	@echo "  preview       - Preview infrastructure changes"
	@echo "  deploy        - Deploy infrastructure (pushes image and updates Lambda functions)"
	@echo "  deploy-infra  - Deploy infrastructure only (no image build)"
	@echo "  destroy       - Destroy all infrastructure"
	@echo "  clean         - Clean up Docker images and containers"
	@echo "  logs          - View Lambda function logs"
	@echo "  test          - Test the API endpoints"
	@echo "  test-auth     - Test authorization flow specifically"
	@echo "  update-image  - Push new image and redeploy infrastructure (recommended for code changes)"

# Install dependencies
install:
	@echo "Installing Python dependencies..."
	uv sync
	@echo "Installing Pulumi dependencies..."
	cd infrastructure && source ../.venv/bin/activate && pip install -r requirements.txt
	@echo "Setting up AWS CLI (if needed)..."
	@which aws || echo "Please install AWS CLI: https://aws.amazon.com/cli/"

# Login to ECR
docker-login:
	@echo "Logging into AWS ECR..."
	@AWS_REGION=$$(aws configure get region || echo "us-east-1"); \
	AWS_ACCOUNT_ID=$$(aws sts get-caller-identity --query Account --output text); \
	echo "Logging into $$AWS_ACCOUNT_ID.dkr.ecr.$$AWS_REGION.amazonaws.com"; \
	mkdir -p ~/.docker; \
	echo '{"credsStore":""}' > ~/.docker/config.json; \
	aws ecr get-login-password --region $$AWS_REGION | docker login --username AWS --password-stdin $$AWS_ACCOUNT_ID.dkr.ecr.$$AWS_REGION.amazonaws.com

# Start Docker daemon (for systems without Docker Desktop)
start-docker:
	@echo "Attempting to start Docker..."
	@if command -v brew >/dev/null 2>&1; then \
		echo "Starting Docker via Homebrew..."; \
		brew services start docker 2>/dev/null || echo "Docker service not available via Homebrew"; \
	fi
	@if [ -f /Applications/Docker.app/Contents/MacOS/Docker ]; then \
		echo "Starting Docker Desktop..."; \
		open -a Docker; \
	fi
	@echo "Waiting for Docker to start..."
	@for i in $$(seq 1 30); do \
		if docker info >/dev/null 2>&1; then \
			echo "Docker is now running!"; \
			break; \
		fi; \
		echo "Waiting... ($$i/30)"; \
		sleep 2; \
	done

# Check if Docker is running
check-docker:
	@echo "Checking if Docker is running..."
	@docker context use colima >/dev/null 2>&1 || true
	@docker info >/dev/null 2>&1 || (echo "Docker is not running. Run 'make start-docker' or start Docker manually." && exit 1)

# Build Docker image locally
build-image: check-docker
	@echo "Building Docker image..."
	@docker context use colima >/dev/null 2>&1 || true
	docker build -t debt-management-backend:latest .

# Get ECR repository URL and push image with content-based tag
push-image: build-image
	@echo "Getting ECR repository URL..."
	@docker context use colima >/dev/null 2>&1 || true
	@ECR_URL=$$(cd infrastructure && source ../.venv/bin/activate && export PATH=$$PATH:/Users/davidnagar/.pulumi/bin && pulumi stack output ecr_repository_url 2>/dev/null || echo ""); \
	if [ -z "$$ECR_URL" ]; then \
		echo "ECR repository not found. Please deploy infrastructure first with 'make deploy-infra'"; \
		exit 1; \
	fi; \
	echo "Generating content-based image tag..."; \
	IMAGE_TAG=$$(cd infrastructure && python3 get_image_tag.py); \
	echo "Using image tag: $$IMAGE_TAG"; \
	echo "$$IMAGE_TAG" > infrastructure/image_tag.txt; \
	echo "Tagging and pushing image to $$ECR_URL..."; \
	docker tag debt-management-backend:latest $$ECR_URL:$$IMAGE_TAG; \
	docker push $$ECR_URL:$$IMAGE_TAG; \
	echo "Image pushed successfully with tag: $$IMAGE_TAG"

# Preview infrastructure changes
preview:
	@echo "Previewing infrastructure changes..."
	cd infrastructure && source ../.venv/bin/activate && export PATH=$$PATH:/Users/davidnagar/.pulumi/bin && pulumi preview

# Deploy infrastructure only (without building image)
deploy-infra:
	@echo "Deploying infrastructure only..."
	cd infrastructure && source ../.venv/bin/activate && export PATH=$$PATH:/Users/davidnagar/.pulumi/bin && pulumi up --yes

# Full deploy (build image, push, then deploy infrastructure)
# With content-based tagging, Pulumi will automatically detect changes and update Lambda functions
deploy: docker-login push-image deploy-infra
	@echo "Full deployment complete!"

# Legacy update commands - no longer needed with content-based tagging
# Pulumi now automatically detects when Lambda functions need updates
update-lambda-images:
	@echo "⚠️  WARNING: This command is deprecated with content-based image tagging."
	@echo "Use 'make deploy' instead - Pulumi will automatically update Lambda functions when code changes."

# Update image and redeploy infrastructure (recommended approach)
update-image: docker-login push-image deploy-infra
	@echo "Image update and infrastructure deployment complete!"

# Destroy infrastructure
destroy:
	@echo "Destroying infrastructure..."
	cd infrastructure && source ../.venv/bin/activate && export PATH=$$PATH:/Users/davidnagar/.pulumi/bin && pulumi destroy --yes

# Clean up Docker resources
clean:
	@echo "Cleaning up Docker resources..."
	docker system prune -f
	docker image prune -f

# View logs for a specific function (usage: make logs FUNCTION=healthz)
logs:
	@if [ -z "$(FUNCTION)" ]; then \
		echo "Usage: make logs FUNCTION=<function_name>"; \
		echo "Available functions: healthz, create-user, get-user, create-debt, get-debt, list-debts, update-debt, delete-debt, authorizer"; \
	else \
		aws logs tail "/aws/lambda/debt-management-$(FUNCTION)" --follow; \
	fi

# Test API endpoints
test:
	@echo "Testing API endpoints..."
	@API_URL=$$(cd infrastructure && source ../.venv/bin/activate && export PATH=$$PATH:/Users/davidnagar/.pulumi/bin && pulumi stack output api_url); \
	echo "API URL: $$API_URL"; \
	echo ""; \
	echo "=== Testing public endpoints (no auth required) ==="; \
	echo "1. Testing health endpoint..."; \
	curl -s "$$API_URL/healthz" | jq . || curl -s "$$API_URL/healthz"; \
	echo ""; \
	echo "2. Testing login endpoint..."; \
	curl -s -X POST "$$API_URL/login" \
		-H "Content-Type: application/json" \
		-d '{"username":"testuser","password":"testpassword123"}' | jq . || echo "Login test failed"; \
	echo ""; \
	echo "=== Testing protected endpoints (should fail without auth) ==="; \
	echo "3. Testing protected endpoint without auth (should fail)..."; \
	curl -s "$$API_URL/users/testuser" | jq . || curl -s "$$API_URL/users/testuser"; \
	echo ""; \
	echo "=== Testing full auth flow ==="; \
	echo "4. Creating user, logging in, and testing debt operations..."; \
	echo "Creating user..."; \
	curl -s -X POST "$$API_URL/users" \
		-H "Content-Type: application/json" \
		-d '{"username":"authtest","email":"authtest@example.com","full_name":"Auth Test","password":"testpass123"}' | jq . || echo "User creation failed"; \
	echo ""; \
	echo "Logging in to get token..."; \
	TOKEN=$$(curl -s -X POST "$$API_URL/login" \
		-H "Content-Type: application/json" \
		-d '{"username":"authtest","password":"testpass123"}' | jq -r '.token // empty'); \
	if [ -n "$$TOKEN" ] && [ "$$TOKEN" != "null" ]; then \
		echo "Token received: $$TOKEN"; \
		echo ""; \
		echo "Testing user endpoint..."; \
		curl -s "$$API_URL/users/authtest" \
			-H "Authorization: Bearer $$TOKEN" | jq . || curl -s "$$API_URL/users/authtest" -H "Authorization: Bearer $$TOKEN"; \
		echo ""; \
		echo "Creating a debt..."; \
		DEBT_RESPONSE=$$(curl -s -X POST "$$API_URL/debts" \
			-H "Authorization: Bearer $$TOKEN" \
			-H "Content-Type: application/json" \
			-d '{"debt_name":"Test Credit Card","principal":1000,"interest_rate":15.99,"start_date":"2024-01-01T00:00:00Z","payment_frequency":"monthly","current_balance":800,"creditor":"Test Bank"}'); \
		echo "$$DEBT_RESPONSE" | jq .; \
		DEBT_ID=$$(echo "$$DEBT_RESPONSE" | jq -r '.data.debt_id // empty'); \
		if [ -n "$$DEBT_ID" ] && [ "$$DEBT_ID" != "null" ]; then \
			echo ""; \
			echo "Getting debt by ID: $$DEBT_ID"; \
			curl -s "$$API_URL/debts/$$DEBT_ID" \
				-H "Authorization: Bearer $$TOKEN" | jq .; \
			echo ""; \
			echo "Listing all debts..."; \
			curl -s "$$API_URL/debts" \
				-H "Authorization: Bearer $$TOKEN" | jq .; \
		fi; \
	else \
		echo "Failed to get token"; \
	fi

# Test authorization specifically
test-auth:
	@echo "Testing authorization flow..."
	@API_URL=$$(cd infrastructure && source ../.venv/bin/activate && export PATH=$$PATH:/Users/davidnagar/.pulumi/bin && pulumi stack output api_url); \
	echo "API URL: $$API_URL"; \
	echo ""; \
	echo "1. Testing endpoint without authorization (should fail)..."; \
	curl -s -w "\nHTTP Status: %{http_code}\n" "$$API_URL/users/testuser"; \
	echo ""; \
	echo "2. Testing endpoint with invalid token (should fail)..."; \
	curl -s -w "\nHTTP Status: %{http_code}\n" "$$API_URL/users/testuser" \
		-H "Authorization: Bearer invalid-token"; \
	echo ""; \
	echo "3. Getting valid token and testing protected endpoint..."; \
	TOKEN=$$(curl -s -X POST "$$API_URL/login" \
		-H "Content-Type: application/json" \
		-d '{"username":"testuser","password":"testpassword123"}' | jq -r '.token // empty'); \
	if [ -n "$$TOKEN" ] && [ "$$TOKEN" != "null" ]; then \
		echo "Valid token received"; \
		echo "Testing protected endpoint with valid token..."; \
		curl -s -w "\nHTTP Status: %{http_code}\n" "$$API_URL/users/testuser" \
			-H "Authorization: Bearer $$TOKEN"; \
	else \
		echo "Failed to get valid token. Make sure user 'testuser' exists."; \
	fi

# Get stack outputs
outputs:
	@cd infrastructure && source ../.venv/bin/activate && export PATH=$$PATH:/Users/davidnagar/.pulumi/bin && pulumi stack output

# Get API URL
api-url:
	@cd infrastructure && source ../.venv/bin/activate && export PATH=$$PATH:/Users/davidnagar/.pulumi/bin && pulumi stack output api_url

# Get ECR repository URL
ecr-url:
	@cd infrastructure && source ../.venv/bin/activate && export PATH=$$PATH:/Users/davidnagar/.pulumi/bin && pulumi stack output ecr_repository_url

# Development helpers
dev-setup: install
	@echo "Setting up development environment..."
	@echo "Creating .env file if it doesn't exist..."
	@touch .env
	@echo "Development setup complete!"

# Build Docker image locally for testing
build-local:
	@echo "Building Docker image locally..."
	docker build -t debt-management-local .

# Run local container for testing
run-local: build-local
	@echo "Running container locally..."
	docker run --rm -p 9000:8080 debt-management-local

# Format code
format:
	@echo "Formatting code..."
	uv run ruff format .
	uv run isort .

# Lint code
lint:
	@echo "Linting code..."
	uv run ruff check .

# Security scan (if you want to add this later)
security-scan:
	@echo "Running security scan..."
	@echo "Consider adding: bandit, safety, or other security tools"

# Backup current deployment
backup:
	@echo "Creating backup of current deployment..."
	@TIMESTAMP=$$(date +%Y%m%d_%H%M%S); \
	cd infrastructure && source ../.venv/bin/activate && export PATH=$$PATH:/Users/davidnagar/.pulumi/bin && pulumi stack export > "../backups/stack_backup_$$TIMESTAMP.json"
	@echo "Backup created in backups/ directory"

# Restore from backup (usage: make restore BACKUP=filename.json)
restore:
	@if [ -z "$(BACKUP)" ]; then \
		echo "Usage: make restore BACKUP=<backup_filename.json>"; \
		ls -la backups/; \
	else \
		cd infrastructure && source ../.venv/bin/activate && export PATH=$$PATH:/Users/davidnagar/.pulumi/bin && pulumi stack import "../backups/$(BACKUP)"; \
	fi 