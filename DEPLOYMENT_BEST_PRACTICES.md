# Docker Lambda Deployment Best Practices

## Overview

This project implements industry best practices for deploying Docker-based AWS Lambda functions using Pulumi. The key innovation is **content-based image tagging** that ensures Lambda functions are automatically updated when code changes.

## The Problem with `:latest` Tags

Traditional Docker deployments often use the `:latest` tag, but this creates problems with Lambda functions:

1. **No Change Detection**: Pulumi doesn't know when the image content changes
2. **Manual Updates Required**: You have to manually update Lambda function code
3. **Inconsistent Deployments**: Different environments might have different versions of "latest"
4. **No Rollback Capability**: Can't easily identify or rollback to specific versions

## Our Solution: Content-Based Image Tagging

### How It Works

1. **Content Hashing**: Generate a hash based on all source code files
2. **Timestamp Integration**: Include timestamp to ensure uniqueness
3. **Automatic Detection**: Pulumi automatically detects when the image URI changes
4. **Seamless Updates**: Lambda functions are updated automatically during deployment

### Tag Format

```
{timestamp}-{content_hash}
Example: 20250526-145140-9f6a1a2a
```

- **Timestamp**: `YYYYMMDD-HHMMSS` for chronological ordering
- **Content Hash**: First 8 characters of MD5 hash of all source files
- **Uniqueness**: Even identical code gets different tags due to timestamp

### Files Included in Hash

The content hash includes:
- `Dockerfile` - Container definition changes
- `pyproject.toml` - Dependency changes  
- `uv.lock` - Exact dependency versions
- `main.py` - Main application entry point
- `authorizer.py` - Authorization logic
- All `.py` files in:
  - `handlers/` - API endpoint handlers
  - `models/` - Data models and validation
  - `services/` - Business logic and external integrations
  - `utils/` - Shared utilities

## Implementation Details

### 1. Standalone Tag Generation Script

**File**: `infrastructure/get_image_tag.py`

```python
def get_content_hash():
    """Generate a hash based on the content of the source code."""
    # Hash all relevant source files
    # Include timestamp for uniqueness
    # Return formatted tag
```

### 2. Pulumi Integration

**File**: `infrastructure/__main__.py`

```python
# Use content-based image tag to force updates when code changes
image_tag = get_content_hash()
image_uri = ecr_repository.repository_url.apply(lambda url: f"{url}:{image_tag}")
```

### 3. Makefile Integration

**File**: `Makefile`

```bash
# Generate content-based image tag and push to ECR
IMAGE_TAG=$(cd infrastructure && python3 get_image_tag.py)
docker tag debt-management-backend:latest $ECR_URL:$IMAGE_TAG
docker push $ECR_URL:$IMAGE_TAG
```

## Deployment Workflow

### For Code Changes

```bash
# 1. Make your code changes
vim handlers/debts.py

# 2. Deploy with automatic Lambda updates
make deploy
```

**What happens:**
1. New content hash is generated based on changed files
2. Docker image is built and tagged with new hash
3. Image is pushed to ECR with unique tag
4. Pulumi detects the new image URI
5. All Lambda functions are automatically updated
6. API Gateway continues to work seamlessly

### For Infrastructure Changes

```bash
# Preview infrastructure changes
make preview

# Deploy infrastructure only (no image build)
make deploy-infra
```

### For Quick Code Updates

```bash
# Build, push, and update Lambda functions
make update-image
```

## Benefits

### 1. **Automatic Updates**
- No manual Lambda function updates required
- Pulumi handles all the complexity
- Consistent across all environments

### 2. **Version Tracking**
- Every deployment has a unique, identifiable tag
- Easy to see what version is deployed
- Content hash shows if code actually changed

### 3. **Rollback Capability**
```bash
# See deployment history
pulumi stack history

# Rollback to previous version
pulumi stack select dev
pulumi refresh  # Get current state
# Update image_tag in __main__.py to previous version
pulumi up
```

### 4. **Development Efficiency**
- Single command deployment: `make deploy`
- No need to remember manual update steps
- Faster iteration cycles

### 5. **Production Safety**
- Deterministic deployments
- No "latest" tag ambiguity
- Clear audit trail of what was deployed when

## Monitoring and Debugging

### Check Current Deployment

```bash
# See current image tag and URI
make outputs

# Output includes:
# image_tag: "20250526-145140-9f6a1a2a"
# image_uri: "065270716773.dkr.ecr.us-east-1.amazonaws.com/debt-management-backend:20250526-145140-9f6a1a2a"
```

### Verify Lambda Function Updates

```bash
# Check if Lambda functions are using the latest image
aws lambda get-function --function-name debt-management-healthz-function \
  --query 'Code.ImageUri'
```

### View Deployment Changes

```bash
# Preview what will change
make preview

# Look for: [diff: ~imageUri,lastModified]
```

## Comparison with Other Approaches

| Approach | Pros | Cons | Use Case |
|----------|------|------|----------|
| **`:latest` tag** | Simple | No change detection, manual updates | Development only |
| **Manual versioning** | Full control | Error-prone, requires discipline | Small teams |
| **Git SHA tags** | Traceable | Doesn't reflect actual content | CI/CD pipelines |
| **Content-based tags** ✅ | Automatic, accurate, traceable | Slightly more complex setup | Production systems |

## Best Practices

### 1. **Always Use `make deploy`**
- Ensures image and infrastructure are in sync
- Handles all the complexity automatically

### 2. **Monitor Outputs**
- Check `image_tag` output to verify deployments
- Use for debugging and audit trails

### 3. **Test Before Deploy**
```bash
# Test locally first
make build-local
make run-local

# Then deploy
make deploy
```

### 4. **Use Preview for Large Changes**
```bash
# Always preview infrastructure changes
make preview

# Review the changes before applying
make deploy-infra
```

## Troubleshooting

### Issue: Lambda Functions Not Updating

**Symptoms**: Code changes not reflected in Lambda functions

**Solution**: 
1. Check if image was pushed: `make ecr-url` and verify in AWS Console
2. Verify tag generation: `cd infrastructure && python3 get_image_tag.py`
3. Check Pulumi preview: `make preview` (should show `~imageUri` changes)

### Issue: Build Failures

**Symptoms**: Docker build or push fails

**Solution**:
1. Check Docker is running: `make check-docker`
2. Verify ECR login: `make docker-login`
3. Check disk space and Docker resources

### Issue: Tag Generation Errors

**Symptoms**: Same tag generated repeatedly

**Solution**:
1. Verify script works: `cd infrastructure && python3 get_image_tag.py`
2. Check file permissions on source files
3. Ensure timestamp is updating (system clock)

## Migration from Legacy Approaches

If migrating from `:latest` tags or manual versioning:

1. **Update Infrastructure**: Replace hardcoded tags with content-based generation
2. **Update CI/CD**: Use `make deploy` instead of manual AWS CLI commands  
3. **Clean Up**: Remove old manual update scripts
4. **Test**: Verify automatic updates work with a small code change

## Future Enhancements

Potential improvements to consider:

1. **Semantic Versioning**: Combine with git tags for release versions
2. **Multi-Stage Builds**: Optimize Docker image size and build time
3. **Blue/Green Deployments**: Use Lambda aliases for zero-downtime deployments
4. **Automated Testing**: Integrate testing into the deployment pipeline

---

This content-based tagging approach represents the current best practice for Docker Lambda deployments, providing the reliability and automation needed for production systems while maintaining the simplicity developers need for rapid iteration. 