#!/usr/bin/env python3
"""
Setup IAM role for AgentCore Runtime deployment.

This script creates an IAM role with necessary permissions for the Student Analytics
Agent to run on Amazon Bedrock AgentCore Runtime.
"""

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path


def run_command(cmd: list[str], check: bool = True) -> tuple[int, str, str]:
    """Run a shell command and return exit code, stdout, and stderr."""
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=check
        )
        return result.returncode, result.stdout, result.stderr
    except subprocess.CalledProcessError as e:
        return e.returncode, e.stdout, e.stderr


def parse_arguments() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Setup IAM role for AgentCore Runtime deployment",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Using command-line argument
  python setup_agentcore_role.py --bucket my-athena-bucket

  # Using environment variable (fallback)
  export ATHENA_S3_BUCKET=my-athena-bucket
  python setup_agentcore_role.py
        """
    )

    parser.add_argument(
        "--bucket",
        type=str,
        help="S3 bucket name for Athena query results (overrides ATHENA_S3_BUCKET env var)"
    )

    return parser.parse_args()


def get_athena_bucket(args: argparse.Namespace) -> str:
    """Get Athena S3 bucket from command-line argument or environment variable."""
    # First try command-line argument
    if args.bucket:
        return args.bucket

    # No bucket specified
    print("Error: Athena S3 bucket not specified")
    print("\nYou must provide the bucket in one of these ways:")
    print("  1. Command-line argument: --bucket <bucket-name>")
    print("  2. Environment variable: export ATHENA_S3_BUCKET=<bucket-name>")
    print("\nExample:")
    print("  python setup_agentcore_role.py --bucket my-athena-bucket")
    sys.exit(1)


def create_trust_policy(output_dir: Path) -> Path:
    """Create the trust policy JSON file."""
    trust_policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Principal": {
                    "Service": [
                        "bedrock-agentcore.amazonaws.com",
                        "bedrock.amazonaws.com",
                        "lambda.amazonaws.com",
                        "ecs-tasks.amazonaws.com"
                    ]
                },
                "Action": "sts:AssumeRole"
            }
        ]
    }

    trust_policy_file = output_dir / "agentcore-trust-policy.json"
    with open(trust_policy_file, 'w') as f:
        json.dump(trust_policy, f, indent=2)

    print(f"✓ Created trust policy: {trust_policy_file}")
    return trust_policy_file


def create_permissions_policy(output_dir: Path, athena_bucket: str) -> Path:
    """Create the permissions policy JSON file with S3 bucket interpolated."""
    permissions_policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Sid": "AthenaQueryExecution",
                "Effect": "Allow",
                "Action": [
                    "athena:StartQueryExecution",
                    "athena:GetQueryExecution",
                    "athena:GetQueryResults",
                    "athena:StopQueryExecution",
                    "athena:GetWorkGroup",
                    "athena:GetDataCatalog",
                    "athena:GetDatabase",
                    "athena:GetTableMetadata",
                    "athena:ListQueryExecutions"
                ],
                "Resource": [
                    "arn:aws:athena:*:*:workgroup/*",
                    "arn:aws:athena:*:*:datacatalog/*"
                ]
            },
            {
                "Sid": "GlueCatalogAccess",
                "Effect": "Allow",
                "Action": [
                    "glue:GetDatabase",
                    "glue:GetTable",
                    "glue:GetPartitions",
                    "glue:GetDatabases",
                    "glue:GetTables"
                ],
                "Resource": [
                    "arn:aws:glue:*:*:catalog",
                    "arn:aws:glue:*:*:database/student_analytics",
                    "arn:aws:glue:*:*:table/student_analytics/*"
                ]
            },
            {
                "Sid": "S3AthenaAccess",
                "Effect": "Allow",
                "Action": [
                    "s3:GetObject",
                    "s3:ListBucket",
                    "s3:GetBucketLocation",
                    "s3:PutObject",
                    "s3:DeleteObject"
                ],
                "Resource": [
                    f"arn:aws:s3:::{athena_bucket}",
                    f"arn:aws:s3:::{athena_bucket}/*"
                ]
            },
            {
                "Sid": "BedrockGlobalInferenceAccess",
                "Effect": "Allow",
                "Action": [
                    "bedrock:InvokeModel",
                    "bedrock:InvokeModelWithResponseStream"
                ],
                "Resource": [
                    "arn:aws:bedrock:*:*:foundation-model/anthropic.claude-*",
                    "arn:aws:bedrock:*:*:inference-profile/global.anthropic.claude-*"
                ]
            },
            {
                "Sid": "CloudWatchLogsAccess1",
                "Effect": "Allow",
                "Action": [
                    "logs:DescribeLogStreams",
                    "logs:CreateLogGroup"
                ],
                "Resource": "arn:aws:logs:*:*:log-group:/aws/bedrock-agentcore/runtimes/*"
            },
            {
                "Sid": "CloudWatchLogsAccess2",
                "Effect": "Allow",
                "Action": [
                    "logs:DescribeLogGroups"
                ],
                "Resource": "arn:aws:logs:*:*:log-group:*"
            },
            {
                "Sid": "CloudWatchLogsAccess3",
                "Effect": "Allow",
                "Action": [
                    "logs:CreateLogStream",
                    "logs:PutLogEvents"
                ],
                "Resource": "arn:aws:logs:*:*:log-group:/aws/bedrock-agentcore/runtimes/*:log-stream:*"
            },
            {
                "Sid": "AgentCoreRuntimeAccess",
                "Effect": "Allow",
                "Action": [
                    "bedrock:GetAgent",
                    "bedrock:InvokeAgent"
                ],
                "Resource": "arn:aws:bedrock:*:*:agent/*"
            },
            {
                "Sid": "ECRImageAccess",
                "Effect": "Allow",
                "Action": [
                    "ecr:GetAuthorizationToken",
                    "ecr:BatchGetImage",
                    "ecr:GetDownloadUrlForLayer",
                    "ecr:BatchCheckLayerAvailability"
                ],
                "Resource": "*"
            }
        ]
    }

    permissions_policy_file = output_dir / "agentcore-permissions-policy.json"
    with open(permissions_policy_file, 'w') as f:
        json.dump(permissions_policy, f, indent=2)

    print(f"✓ Created permissions policy: {permissions_policy_file}")
    return permissions_policy_file


def create_iam_role(role_name: str, trust_policy_file: Path) -> bool:
    """Create the IAM role. Returns True if successful or role already exists."""
    print(f"\nCreating IAM role: {role_name}")

    # Check if role already exists
    code, stdout, stderr = run_command(
        ["aws", "iam", "get-role", "--role-name", role_name],
        check=False
    )

    if code == 0:
        print(f"✓ Role {role_name} already exists")
        return True

    # Create the role
    code, stdout, stderr = run_command([
        "aws", "iam", "create-role",
        "--role-name", role_name,
        "--assume-role-policy-document", f"file://{trust_policy_file}",
        "--description", "IAM role for Student Analytics Agent on AgentCore Runtime"
    ], check=False)

    if code == 0:
        print(f"✓ Created IAM role: {role_name}")
        return True
    else:
        print(f"✗ Failed to create role: {stderr}")
        return False


def attach_policy(role_name: str, policy_name: str, permissions_policy_file: Path) -> bool:
    """Attach the permissions policy to the role."""
    print(f"\nAttaching policy: {policy_name}")

    code, stdout, stderr = run_command([
        "aws", "iam", "put-role-policy",
        "--role-name", role_name,
        "--policy-name", policy_name,
        "--policy-document", f"file://{permissions_policy_file}"
    ], check=False)

    if code == 0:
        print(f"✓ Attached policy: {policy_name}")
        return True
    else:
        print(f"✗ Failed to attach policy: {stderr}")
        return False


def get_role_arn(role_name: str) -> str | None:
    """Get the ARN of the IAM role."""
    code, stdout, stderr = run_command([
        "aws", "iam", "get-role",
        "--role-name", role_name,
        "--query", "Role.Arn",
        "--output", "text"
    ], check=False)

    if code == 0:
        return stdout.strip()
    return None


def main():
    """Main execution function."""
    print("=" * 60)
    print("AgentCore IAM Role Setup")
    print("=" * 60)

    # Parse command-line arguments
    args = parse_arguments()

    # Get project root
    script_dir = Path(__file__).parent
    project_root = script_dir.parent
    output_dir = project_root / "agentcore"

    # Create output directory if it doesn't exist
    output_dir.mkdir(exist_ok=True)

    # Get S3 bucket from command-line or environment
    athena_bucket = get_athena_bucket(args)
    print(f"Using S3 bucket: {athena_bucket}\n")

    # Configuration
    role_name = "StudentAnalyticsAgentCoreRole"
    policy_name = "StudentAnalyticsAgentCorePolicy"

    # Create policy files
    trust_policy_file = create_trust_policy(output_dir)
    permissions_policy_file = create_permissions_policy(output_dir, athena_bucket)

    # Create IAM role
    if not create_iam_role(role_name, trust_policy_file):
        sys.exit(1)

    # Attach permissions policy
    if not attach_policy(role_name, policy_name, permissions_policy_file):
        sys.exit(1)

    # Get and display role ARN
    role_arn = get_role_arn(role_name)
    if role_arn:
        print("\n" + "=" * 60)
        print("✓ Setup Complete!")
        print("=" * 60)
        print(f"\nIAM Role ARN: {role_arn}")
        print(f"\nExport this for AgentCore deployment:")
        print(f"export AGENTCORE_ROLE_ARN={role_arn}")
        print("\nOr add to your .env file:")
        print(f"AGENTCORE_ROLE_ARN={role_arn}")
    else:
        print("\n✗ Failed to retrieve role ARN")
        sys.exit(1)


if __name__ == "__main__":
    main()
