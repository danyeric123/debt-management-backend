import pulumi
import pulumi_aws as aws

# Shared ECR Repository for all Lambda functions
ecr_repository = aws.ecr.Repository(
    "debt-management-repo", name="debt-management-backend", force_delete=True
)

# Export the repository URL
pulumi.export("ecr_repository_url", ecr_repository.repository_url)
