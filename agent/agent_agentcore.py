#!/usr/bin/env python3
"""
Student Analytics AI Agent with Amazon Bedrock AgentCore wrapper.
This version is designed for deployment to AgentCore Runtime.
"""

import os
import sys
import json
import logging
import uuid
from pathlib import Path
from urllib.parse import urlparse
import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

# Configure logging for CloudWatch
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    force=True  # Override any existing config
)

# Suppress verbose Claude Agent SDK output
logging.getLogger("claude_agent_sdk").setLevel(logging.WARNING)

# Create logger for this module
logger = logging.getLogger(__name__)

# Add parent directory to path to import tools
sys.path.insert(0, str(Path(__file__).parent.parent))

from bedrock_agentcore import BedrockAgentCoreApp
from claude_agent_sdk import ClaudeAgentOptions, tool, create_sdk_mcp_server, ClaudeSDKClient
from tools.athena_tools import AthenaQueryExecutor

# Initialize AgentCore app
app = BedrockAgentCoreApp()

# Get environment configuration (used per-request)
ATHENA_DATABASE = os.getenv("ATHENA_DATABASE", "student_analytics")
ATHENA_OUTPUT = os.getenv("ATHENA_OUTPUT_LOCATION", "s3://your-bucket/athena-results/")
AWS_REGION = os.getenv("AWS_REGION", "us-east-1")


def parse_s3_bucket_from_output_location(s3_location: str) -> str | None:
    """Extract bucket name from S3 location string."""
    try:
        parsed = urlparse(s3_location)
        if parsed.scheme == 's3':
            return parsed.netloc
    except Exception as e:
        logger.error(f"Failed to parse S3 location '{s3_location}': {e}")
    return None


def upload_file_to_s3(local_file_path: str, bucket: str, s3_key: str, region: str) -> bool:
    """Upload a file to S3 using SigV4."""
    try:
        config = Config(signature_version='s3v4', region_name=region)
        s3_client = boto3.client('s3', config=config, region_name=region)
        s3_client.upload_file(local_file_path, bucket, s3_key)
        logger.info(f"Uploaded {local_file_path} to s3://{bucket}/{s3_key}")
        return True
    except ClientError as e:
        logger.error(f"Failed to upload {local_file_path} to S3: {e}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error uploading to S3: {e}")
        return False


def generate_signed_url(bucket: str, s3_key: str, region: str, expiration: int = 300) -> str | None:
    """Generate a SigV4 presigned URL for an S3 object."""
    try:
        config = Config(signature_version='s3v4', region_name=region)
        s3_client = boto3.client('s3', config=config, region_name=region)

        url = s3_client.generate_presigned_url(
            'get_object',
            Params={'Bucket': bucket, 'Key': s3_key},
            ExpiresIn=expiration
        )
        logger.info(f"Generated SigV4 signed URL for s3://{bucket}/{s3_key} (expires in {expiration}s)")
        return url
    except ClientError as e:
        logger.error(f"Failed to generate signed URL: {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error generating signed URL: {e}")
        return None


@app.entrypoint
async def main(payload: dict = None):
    """
    Main entrypoint for AgentCore with streaming support.

    Args:
        payload: Request payload containing 'query' field

    Yields:
        Streaming events with agent responses
    """
    # Generate unique request ID for this invocation
    request_id = str(uuid.uuid4())

    # Extract user query from payload
    if payload is None or "query" not in payload:
        yield {
            "error": "Missing 'query' field in payload",
            "example": {
                "query": "How many students are currently enrolled?"
            }
        }
        return

    user_query = payload["query"]

    # Load project context from CLAUDE.md
    project_root = Path(__file__).parent.parent
    claude_md_path = project_root / "CLAUDE.md"

    if not claude_md_path.exists():
        logger.warning("CLAUDE.md not found. Agent will work with limited context.")
        project_context = ""
    else:
        with open(claude_md_path, 'r') as f:
            project_context = f.read()
        logger.info(f"Loaded project context from CLAUDE.md ({len(project_context)} chars)")

    # Initialize Athena executor with configuration
    athena_executor = AthenaQueryExecutor(
        database=ATHENA_DATABASE,
        output_location=ATHENA_OUTPUT,
        results_dir=f"./results/raw/{request_id}",
        region=AWS_REGION
    )

    # Define the Athena query tool using @tool decorator
    @tool("execute_athena_query", "Execute SQL queries against Amazon Athena database and download results", {
        "query": str,
        "local_filename": str
    })
    async def execute_athena_query(args):
        """Execute SQL query on Athena and download results."""
        try:
            query_text = args.get("query", "")
            local_filename = args.get("local_filename", "query_results.csv")

            result = athena_executor.execute_and_download(
                query=query_text,
                local_filename=local_filename
            )

            response_text = f"""Query completed successfully!

Data scanned: {result.get('data_scanned_bytes', 0) / (1024**2):.2f} MB
Execution time: {result.get('execution_time_ms', 0) / 1000:.2f} seconds
Results downloaded to: {result['local_file']}
Query Execution ID: {result['query_execution_id']}"""

            return {
                "content": [
                    {"type": "text", "text": response_text}
                ]
            }

        except Exception as e:
            return {
                "content": [
                    {"type": "text", "text": f"Error executing query: {str(e)}"}
                ],
                "isError": True
            }

    # Create MCP server with the Athena tool
    athena_server = create_sdk_mcp_server(
        name="athena",
        version="1.0.0",
        tools=[execute_athena_query]
    )

    # Configure agent options
    options = ClaudeAgentOptions(
        system_prompt=f"""You are a Student Analytics AI Agent running on Amazon Bedrock AgentCore.

IMPORTANT: This request has ID: {request_id}
- All processed files (visualizations, reports, analysis) must be saved to: results/processed/{request_id}/
- Query results are automatically saved to: results/raw/{request_id}/ by the execute_athena_query tool

{project_context}
""",
        allowed_tools=["Skill", "Read", "Write", "Bash", "mcp__athena__execute_athena_query"],
        mcp_servers={"athena": athena_server},
        setting_sources=["project"],
        cwd=str(project_root),
        max_turns=30
    )

    logger.info("=" * 80)
    logger.info("STUDENT ANALYTICS AI AGENT (AgentCore) - STREAMING MODE")
    logger.info(f"Request ID: {request_id}")
    logger.info("=" * 80)
    logger.info(f"User Query: {user_query}")
    logger.info("-" * 80)

    # Ensure results directories exist
    processed_dir = project_root / "results" / "processed" / request_id
    processed_dir.mkdir(parents=True, exist_ok=True)
    raw_dir = project_root / "results" / "raw" / request_id

    # Parse S3 bucket for uploading results
    s3_bucket = parse_s3_bucket_from_output_location(ATHENA_OUTPUT)
    if s3_bucket:
        logger.info(f"Will upload results to S3 bucket: {s3_bucket}")
    else:
        logger.warning(f"Could not parse S3 bucket from: {ATHENA_OUTPUT}")

    # Run the agent with error handling and streaming
    try:
        async with ClaudeSDKClient(options=options) as client:
            await client.query(user_query)

            async for message in client.receive_response():
                # Log system messages but don't stream them
                if hasattr(message, 'subtype'):
                    if message.subtype == 'init':
                        logger.info("[SYSTEM] Agent initialized")
                        continue
                    elif message.subtype == 'success':
                        duration_s = getattr(message, 'duration_ms', 0) / 1000
                        cost = getattr(message, 'total_cost_usd', 0)
                        turns = getattr(message, 'num_turns', 0)

                        logger.info("=" * 80)
                        logger.info(f"Analysis Complete - Duration: {duration_s:.1f}s | Cost: ${cost:.4f} | Turns: {turns}")
                        logger.info("=" * 80)
                        continue

                # Stream content
                if hasattr(message, 'content'):
                    content_list = message.content if isinstance(message.content, list) else [message.content]

                    for block in content_list:
                        # Text content from assistant - STREAM THIS
                        if hasattr(block, 'text'):
                            logger.info(f"[STREAMING TEXT] {block.text[:100]}...")
                            if block.text.startswith("Base directory for this skill"):
                                first_line = block.text.split('\n', 1)[0]
                                yield '\n' + first_line + '\n'
                            else:
                                yield '\n' + block.text + '\n'

                        # Tool use blocks
                        elif hasattr(block, 'name') and hasattr(block, 'input'):
                            tool_name = block.name
                            logger.info(f"[TOOL USE] {tool_name}")

                            if tool_name == "Skill":
                                skill_name = block.input.get('skill', 'unknown')
                                yield f"\n🎯 Loading skill: {skill_name}\n"

                            elif tool_name == "mcp__athena__execute_athena_query":
                                query_sql = block.input.get('query', '')
                                filename = block.input.get('local_filename', '')

                                yield f"\ninvoking tool: {tool_name}\n"

                                if query_sql:
                                    logger.info(f"[SQL QUERY] {query_sql[:100]}...")
                                    sql_output = f"\n{'─' * 50}\n📊 SQL QUERY\n{'─' * 50}\n{query_sql}\n{'─' * 50}\n\n💾 Saving to: {filename}\n\n⏳ Executing query...\n"
                                    yield sql_output

                        # Log tool results but don't stream
                        elif hasattr(block, 'tool_use_id') and hasattr(block, 'content'):
                            is_error = getattr(block, 'is_error', False)
                            logger.info(f"[TOOL RESULT] Error: {is_error}")

        # After agent completes, upload all files from this request to S3
        logger.info(f"Checking for files to upload for request {request_id}...")

        processed_files = list(processed_dir.glob("*"))
        raw_files = list(raw_dir.glob("*")) if raw_dir.exists() else []

        total_files = len([f for f in processed_files if f.is_file()]) + len([f for f in raw_files if f.is_file()])

        if total_files > 0 and s3_bucket:
            logger.info(f"Found {len([f for f in raw_files if f.is_file()])} raw files and {len([f for f in processed_files if f.is_file()])} processed files")

            generated_files = []

            # Upload raw files
            for file_path in sorted(raw_files):
                if file_path.is_file():
                    s3_key = f"results/raw/{request_id}/{file_path.name}"
                    if upload_file_to_s3(str(file_path), s3_bucket, s3_key, AWS_REGION):
                        signed_url = generate_signed_url(s3_bucket, s3_key, AWS_REGION, expiration=300)
                        if signed_url:
                            generated_files.append({
                                "filename": file_path.name,
                                "type": "raw_data",
                                "url": signed_url,
                                "expires_in_seconds": 300,
                                "s3_location": f"s3://{s3_bucket}/{s3_key}",
                                "request_id": request_id
                            })

            # Upload processed files
            for file_path in sorted(processed_files):
                if file_path.is_file():
                    s3_key = f"results/processed/{request_id}/{file_path.name}"
                    if upload_file_to_s3(str(file_path), s3_bucket, s3_key, AWS_REGION):
                        signed_url = generate_signed_url(s3_bucket, s3_key, AWS_REGION, expiration=300)
                        if signed_url:
                            file_type = "visualization" if file_path.suffix in ['.png', '.jpg', '.jpeg', '.svg'] else "report"
                            generated_files.append({
                                "filename": file_path.name,
                                "type": file_type,
                                "url": signed_url,
                                "expires_in_seconds": 300,
                                "s3_location": f"s3://{s3_bucket}/{s3_key}",
                                "request_id": request_id
                            })

            if generated_files:
                output = {
                    "request_id": request_id,
                    "generated_files": generated_files,
                    "total_count": len(generated_files),
                    "note": "URLs are valid for 5 minutes"
                }
                yield f"\n\n```json\n{json.dumps(output, indent=2)}\n```\n"

    except Exception as e:
        logger.error("=" * 80)
        logger.error("ERROR DURING AGENT EXECUTION")
        logger.error(f"Request ID: {request_id}")
        logger.error(f"Error type: {type(e).__name__}")
        logger.error(f"Error message: {str(e)}")
        import traceback
        logger.error(f"Traceback:\n{traceback.format_exc()}")
        logger.error("=" * 80)

        yield f"Error: {str(e)}"
        return

    logger.info("=" * 80)
    logger.info(f"Streaming Complete - Request ID: {request_id}")
    logger.info("=" * 80)


if __name__ == "__main__":
    app.run()
