import json
from typing import Dict, List, Optional

import pulumi
import pulumi_aws as aws


class DockerLambdaFunction(pulumi.ComponentResource):
    """
    A reusable component that creates a Lambda function using Docker images with:
    - Shared ECR repository and image
    - CloudWatch Log Group
    - IAM Role with basic execution permissions
    - Custom IAM policies
    - Environment variables
    """

    def __init__(
        self,
        name: str,
        handler: str,
        shared_image_uri: pulumi.Input[str],
        environment_vars: Optional[Dict[str, pulumi.Input[str]]] = None,
        additional_policies: Optional[List[pulumi.Input[str]]] = None,
        timeout: int = 30,
        memory_size: int = 128,
        opts: Optional[pulumi.ResourceOptions] = None,
    ):
        super().__init__("custom:aws:DockerLambdaFunction", name, None, opts)

        # CloudWatch Log Group
        self.log_group = aws.cloudwatch.LogGroup(
            f"{name}-log-group",
            name=f"/aws/lambda/{name}",
            retention_in_days=14,
            opts=pulumi.ResourceOptions(parent=self),
        )

        # IAM Role for Lambda
        assume_role_policy = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Action": "sts:AssumeRole",
                    "Effect": "Allow",
                    "Principal": {"Service": "lambda.amazonaws.com"},
                }
            ],
        }

        self.role = aws.iam.Role(
            f"{name}-role",
            assume_role_policy=json.dumps(assume_role_policy),
            opts=pulumi.ResourceOptions(parent=self),
        )

        # Attach basic Lambda execution policy
        self.basic_policy_attachment = aws.iam.RolePolicyAttachment(
            f"{name}-basic-policy",
            role=self.role.name,
            policy_arn="arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole",
            opts=pulumi.ResourceOptions(parent=self),
        )

        # Attach additional policies if provided
        self.additional_policy_attachments = []
        if additional_policies:
            for i, policy_doc in enumerate(additional_policies):
                policy = aws.iam.RolePolicy(
                    f"{name}-policy-{i}",
                    role=self.role.id,
                    policy=policy_doc,
                    opts=pulumi.ResourceOptions(parent=self),
                )
                self.additional_policy_attachments.append(policy)

        # Lambda Function using shared container image
        self.function = aws.lambda_.Function(
            f"{name}-function",
            package_type="Image",
            image_uri=shared_image_uri,
            role=self.role.arn,
            timeout=timeout,
            memory_size=memory_size,
            environment={"variables": environment_vars or {}},
            image_config={"commands": [handler]},
            opts=pulumi.ResourceOptions(parent=self, depends_on=[self.log_group]),
        )

        # Export important attributes
        self.arn = self.function.arn
        self.name = self.function.name
        self.invoke_arn = self.function.invoke_arn

        self.register_outputs(
            {
                "arn": self.arn,
                "name": self.name,
                "invoke_arn": self.invoke_arn,
                "role_arn": self.role.arn,
            }
        )
