#!/usr/bin/env python3
"""
Student Analytics AI Agent with Amazon Bedrock AgentCore wrapper.
This version is designed for deployment to AgentCore Runtime.
"""

import os
import sys
import re
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
from claude_agent_sdk.types import (
    HookMatcher,
    PermissionResultAllow,
    PermissionResultDeny,
    ToolPermissionContext,
)
from tools.athena_tools import AthenaQueryExecutor

# Initialize AgentCore app
app = BedrockAgentCoreApp()

# Get environment configuration (used per-request)
ATHENA_DATABASE = os.getenv("ATHENA_DATABASE", "student_analytics")
ATHENA_OUTPUT = os.getenv("ATHENA_OUTPUT_LOCATION", "s3://your-bucket/athena-results/")
AWS_REGION = os.getenv("AWS_REGION", "us-east-1")


def parse_s3_bucket_from_output_location(s3_location: str) -> str | None:
    """
    Extract bucket name from S3 location string.

    Args:
        s3_location: S3 location like 's3://bucket-name/path/'

    Returns:
        Bucket name or None if invalid
    """
    try:
        parsed = urlparse(s3_location)
        if parsed.scheme == 's3':
            return parsed.netloc
    except Exception as e:
        logger.error(f"Failed to parse S3 location '{s3_location}': {e}")
    return None


def upload_file_to_s3(local_file_path: str, bucket: str, s3_key: str, region: str) -> bool:
    """
    Upload a file to S3 using SigV4.

    Args:
        local_file_path: Path to local file
        bucket: S3 bucket name
        s3_key: S3 object key (path within bucket)
        region: AWS region

    Returns:
        True if successful, False otherwise
    """
    try:
        # Configure client to use SigV4
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
    """
    Generate a SigV4 presigned URL for an S3 object.

    Args:
        bucket: S3 bucket name
        s3_key: S3 object key
        region: AWS region
        expiration: URL expiration time in seconds (default 300 = 5 minutes, max 604800 = 7 days)

    Returns:
        Presigned URL string with SigV4 signature or None if failed
    """
    try:
        # Configure client to explicitly use SigV4 signature
        config = Config(
            signature_version='s3v4',
            region_name=region
        )
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

async def handle_ask_user_question_agentcore(input_data: dict) -> PermissionResultAllow:
    """
    Handle AskUserQuestion in AgentCore by outputting structured JSON and exiting.

    In AgentCore serverless environment, we cannot block for user input.
    Instead, we output the questions as structured JSON and return,
    letting invoke_agentcore.py handle the user prompting and re-invocation.

    Args:
        input_data: Dictionary containing 'questions' array from Claude

    Returns:
        PermissionResultAllow with the questions for JSON output
    """
    # In AgentCore, we just allow the tool and let it output JSON
    # The questions will be captured in the stream and parsed by invoke_agentcore.py
    return PermissionResultAllow(updated_input=input_data)


@app.entrypoint
async def main(payload: dict = None):
    """
    Main entrypoint for AgentCore with streaming support.
    Handles incoming requests with user queries and streams responses.

    Args:
        payload: Request payload containing 'query' field

    Yields:
        Streaming events with agent responses
    """
    # Generate unique request ID for this invocation
    request_id = str(uuid.uuid4())

    # Define the can_use_tool callback for handling permissions and clarification questions
    async def can_use_tool(
        tool_name: str, input_data: dict, context: ToolPermissionContext
    ) -> PermissionResultAllow | PermissionResultDeny:
        """Handle tool permission requests and clarification questions."""

        # Handle AskUserQuestion tool - output structured JSON for invoke_agentcore.py
        if tool_name == "AskUserQuestion":
            logger.info("[ASK_USER_QUESTION] Tool called - will output structured questions")
            return await handle_ask_user_question_agentcore(input_data)

        # Auto-approve all other tools (Read, Write, Bash, execute_athena_query)
        return PermissionResultAllow(updated_input=input_data)

    # Dummy hook required for Python streaming mode to keep stream open for can_use_tool
    async def can_use_tool_hook(input_data, tool_use_id, context):
        return {"continue_": True}

    # Extract user query from payload
    if payload is None or "query" not in payload:
        yield {
            "error": "Missing 'query' field in payload",
            "example": {
                "query": "How many students are currently enrolled?",
                "claude_agent_sdk_session_id": "(Optional) Claude Agent SDK session id to resume a previous session"
            }
        }
        return

    user_query = payload["query"]

    # Extract optional Claude Agent SDK Session ID for resuming previous sessions
    resume_session_id = payload.get("claude_agent_sdk_session_id", None)
    if resume_session_id:
        logger.info(f"[RESUME] Resuming Claude Agent SDK session: {resume_session_id}")
    else:
        logger.info("[NEW SESSION] Starting new Claude Agent SDK session")

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
    # Pass full path with request_id included
    athena_executor = AthenaQueryExecutor(
        database=ATHENA_DATABASE,
        output_location=ATHENA_OUTPUT,
        results_dir=f"./results/raw/{request_id}",
        region=AWS_REGION
    )

    # Define the Athena query tool using @tool decorator
    # Configuration is captured via closure
    @tool("execute_athena_query", "Execute SQL queries against Amazon Athena database and download results", {
        "query": str,
        "local_filename": str
    })
    async def execute_athena_query(args):
        """Execute SQL query on Athena and download results."""
        try:
            query_text = args.get("query", "")
            local_filename = args.get("local_filename", "query_results.csv")

            # Execute query and download results
            result = athena_executor.execute_and_download(
                query=query_text,
                local_filename=local_filename
            )

            # Format response as human-readable text
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
    options_dict = {
        "system_prompt": f"""You are a Student Analytics AI Agent running on Amazon Bedrock AgentCore.

IMPORTANT: This request has ID: {request_id}
- All processed files (visualizations, reports, analysis) must be saved to: results/processed/{request_id}/
- Query results are automatically saved to: results/raw/{request_id}/ by the execute_athena_query tool

{project_context}

**CRITICAL - Query Clarification Protocol:**
When a user query is ambiguous or could be interpreted multiple ways AFTER loading skills, you should ask for clarification BEFORE creating and executing any SQL query.

To ask clarification questions:
1. Use the AskUserQuestion tool to present your questions to the user
2. Provide 2-4 clear options for each question with descriptive labels
3. DO NOT execute any queries before you receive the user's answers
""",
        "allowed_tools": ["Skill", "Read", "Write", "Bash", "AskUserQuestion", "mcp__athena__execute_athena_query"],
        "mcp_servers": {"athena": athena_server},
        "can_use_tool": can_use_tool,
        "hooks": {"PreToolUse": [HookMatcher(matcher=None, hooks=[can_use_tool_hook])]},
        "setting_sources": ["project"],
        "cwd": str(Path(__file__).parent.parent),
        "max_turns": 30
    }

    # Add resume parameter if session ID is provided
    if resume_session_id:
        options_dict["resume"] = resume_session_id
        logger.info(f"Added resume parameter with session ID: {resume_session_id}")

    options = ClaudeAgentOptions(**options_dict)

    logger.info("=" * 80)
    logger.info("STUDENT ANALYTICS AI AGENT (AgentCore) - STREAMING MODE")
    logger.info(f"Request ID: {request_id}")
    logger.info("=" * 80)
    logger.info(f"User Query: {user_query}")
    logger.info("-" * 80)

    # Ensure processed results directory exists with request_id subdirectory
    # (raw directory is created by AthenaQueryExecutor)
    processed_dir = project_root / "results" / "processed" / request_id
    processed_dir.mkdir(parents=True, exist_ok=True)
    raw_dir = project_root / "results" / "raw" / request_id  # For reference in S3 upload code

    # Parse S3 bucket for uploading results
    s3_bucket = parse_s3_bucket_from_output_location(ATHENA_OUTPUT)
    if s3_bucket:
        logger.info(f"Will upload results to S3 bucket: {s3_bucket}")
    else:
        logger.warning(f"Could not parse S3 bucket from: {ATHENA_OUTPUT}")

    # Run the agent with error handling and streaming
    try:
        # Track Claude Agent SDK Session ID
        claude_agent_sdk_session_id = None

        # Use ClaudeSDKClient
        async with ClaudeSDKClient(options=options) as client:
            await client.query(user_query)

            # Process response
            async for message in client.receive_response():

                # Log full message as text
                if isinstance(message, dict):
                    logger.info(f"Full message (dict): {str(message)}")
                else:
                    logger.info(f"Full message (object): {str(message)}")
                    logger.info(f"Message attributes: {str(vars(message)) if hasattr(message, '__dict__') else 'No attributes'}")

                # Log messages for debugging
                logger.debug(f"Message type: {type(message)}")

                # Log system messages but don't stream them
                if hasattr(message, 'subtype'):
                    if message.subtype == 'init':
                        # Capture Claude Agent SDK Session ID
                        claude_agent_sdk_session_id = getattr(message, 'session_id', None) or getattr(message, 'data', {}).get('session_id', None)
                        logger.info(f"[SYSTEM] Agent initialized - Claude Agent SDK Session ID: {claude_agent_sdk_session_id}")
                        yield f"\nClaude Agent SDK Session ID: {claude_agent_sdk_session_id}\n"
                        continue
                    elif message.subtype == 'success':
                        # Log final summary with metrics
                        duration_s = getattr(message, 'duration_ms', 0) / 1000
                        cost = getattr(message, 'total_cost_usd', 0)
                        turns = getattr(message, 'num_turns', 0)

                        logger.info("=" * 80)
                        logger.info(f"Analysis Complete - Duration: {duration_s:.1f}s | Cost: ${cost:.4f} | Turns: {turns}")
                        logger.info("=" * 80)
                        continue

                # Stream ONLY text content
                if hasattr(message, 'content'):
                    content_list = message.content if isinstance(message.content, list) else [message.content]

                    for block in content_list:
                        # Text content from assistant - STREAM THIS
                        if hasattr(block, 'text'):
                            logger.info(f"[STREAMING TEXT] {block.text[:100]}...")

                            # Yield only the text content, no wrapper
                            # Check if text starts with "Base directory for this skill"
                            if block.text.startswith("Base directory for this skill"):
                                # Only yield the first line (before the first \n) with newline at the end
                                first_line = block.text.split('\n', 1)[0]
                                yield '\n' + first_line + '\n'
                            else:
                                # Yield the whole block.text
                                yield '\n'+ block.text + '\n'

                        # Tool use blocks - extract and stream SQL for execute_athena_query
                        elif hasattr(block, 'name') and hasattr(block, 'input'):
                            tool_name = block.name
                            logger.info(f"[TOOL USE] {tool_name}")

                            # For Skill tool, display friendly message
                            if tool_name == "Skill":
                                skill_name = block.input.get('skill', 'unknown')
                                yield f"\n🎯 Loading skill: {skill_name}\n"

                            # For AskUserQuestion tool, capture questions for structured output
                            elif tool_name == "AskUserQuestion":
                                ask_user_question_data = block.input
                                num_questions = len(block.input.get('questions', []))
                                logger.info(f"[ASK_USER_QUESTION] Captured {num_questions} questions for structured output")
                                yield f"\n❓ Claude is asking {num_questions} clarification question(s)...\n"
                                
                                clarification_output = {
                                    "request_id": request_id,
                                    "claude_agent_sdk_session_id": claude_agent_sdk_session_id,
                                    "status": "clarification_needed",
                                    "questions": ask_user_question_data.get("questions", []),
                                    "message": "Please answer the questions and invoke again with your answers."
                                }
                                clarification_output_string = f"\n\n```json\n{json.dumps(clarification_output, indent=2)}\n```\n"
                                logger.info(clarification_output_string)
                                yield clarification_output_string
                                return
                            # For execute_athena_query tool, extract and stream SQL
                            elif tool_name == "mcp__athena__execute_athena_query":
                                query_sql = block.input.get('query', '')
                                filename = block.input.get('local_filename', '')

                                # Yield tool invocation message
                                yield f"\ninvoking tool: {tool_name}\n"

                                if query_sql:
                                    logger.info(f"[SQL QUERY] {query_sql[:100]}...")
                                    # Format SQL in a box for streaming
                                    sql_output = f"\n{'─' * 50}\n📊 SQL QUERY\n{'─' * 50}\n{query_sql}\n{'─' * 50}\n\n💾 Saving to: {filename}\n\n⏳ Executing query...\n"
                                    yield sql_output

                        # Log tool results but don't stream
                        elif hasattr(block, 'tool_use_id') and hasattr(block, 'content'):
                            is_error = getattr(block, 'is_error', False)
                            logger.info(f"[TOOL RESULT] Error: {is_error}")

        # After agent completes, upload all files from this request to S3
        logger.info(f"Checking for files to upload for request {request_id}...")

        # Get all files from request-specific directories
        processed_files = list(processed_dir.glob("*"))
        raw_files = list(raw_dir.glob("*"))

        total_files = len([f for f in processed_files if f.is_file()]) + len([f for f in raw_files if f.is_file()])

        if total_files > 0:
            logger.info(f"Found {len([f for f in raw_files if f.is_file()])} raw files and {len([f for f in processed_files if f.is_file()])} processed files for request {request_id}")

            # Upload to S3 and generate signed URLs
            if s3_bucket:
                generated_files = []

                # Upload raw files
                for file_path in sorted(raw_files):
                    if file_path.is_file():
                        # Create S3 key: results/raw/{request_id}/{filename}
                        s3_key = f"results/raw/{request_id}/{file_path.name}"

                        # Upload to S3
                        if upload_file_to_s3(str(file_path), s3_bucket, s3_key, AWS_REGION):
                            # Generate signed URL (5 minutes expiration)
                            signed_url = generate_signed_url(s3_bucket, s3_key, AWS_REGION, expiration=300)

                            if signed_url:
                                # Add to list
                                generated_files.append({
                                    "filename": file_path.name,
                                    "type": "raw_data",
                                    "url": signed_url,
                                    "expires_in_seconds": 300,
                                    "s3_location": f"s3://{s3_bucket}/{s3_key}",
                                    "request_id": request_id
                                })
                                logger.info(f"Uploaded raw file {file_path.name} with request_id {request_id}")
                            else:
                                logger.warning(f"Failed to generate signed URL for {file_path.name}")
                        else:
                            logger.warning(f"Failed to upload {file_path.name} to S3")

                # Upload processed files
                for file_path in sorted(processed_files):
                    if file_path.is_file():
                        # Create S3 key: results/processed/{request_id}/{filename}
                        s3_key = f"results/processed/{request_id}/{file_path.name}"

                        # Upload to S3
                        if upload_file_to_s3(str(file_path), s3_bucket, s3_key, AWS_REGION):
                            # Generate signed URL (5 minutes expiration)
                            signed_url = generate_signed_url(s3_bucket, s3_key, AWS_REGION, expiration=300)

                            if signed_url:
                                # Determine file type
                                file_type = "visualization" if file_path.suffix in ['.png', '.jpg', '.jpeg', '.svg'] else "report"

                                # Add to list
                                generated_files.append({
                                    "filename": file_path.name,
                                    "type": file_type,
                                    "url": signed_url,
                                    "expires_in_seconds": 300,
                                    "s3_location": f"s3://{s3_bucket}/{s3_key}",
                                    "request_id": request_id
                                })
                                logger.info(f"Uploaded processed file {file_path.name} with request_id {request_id}")
                            else:
                                logger.warning(f"Failed to generate signed URL for {file_path.name}")
                        else:
                            logger.warning(f"Failed to upload {file_path.name} to S3")

                # Yield structured JSON output
                if generated_files:
                    output = {
                        "request_id": request_id,
                        "claude_agent_sdk_session_id": claude_agent_sdk_session_id,
                        "generated_files": generated_files,
                        "total_count": len(generated_files),
                        "note": "URLs are valid for 5 minutes"
                    }
                    yield f"\n\n```json\n{json.dumps(output, indent=2)}\n```\n"
            else:
                error_output = {
                    "request_id": request_id,
                    "claude_agent_sdk_session_id": claude_agent_sdk_session_id,
                    "error": "S3 bucket not configured",
                    "message": "Could not upload files - S3 bucket not configured properly",
                    "local_paths": [f"results/raw/{request_id}/", f"results/processed/{request_id}/"]
                }
                yield f"\n\n```json\n{json.dumps(error_output, indent=2)}\n```\n"
        else:
            logger.info(f"No files generated for request {request_id}")

    except Exception as e:
        logger.error("=" * 80)
        logger.error("ERROR DURING AGENT EXECUTION")
        logger.error(f"Request ID: {request_id}")
        logger.error("=" * 80)
        logger.error(f"Error type: {type(e).__name__}")
        logger.error(f"Error message: {str(e)}")
        import traceback
        logger.error(f"Traceback:\n{traceback.format_exc()}")
        logger.error("=" * 80)

        # Stream error message as text
        yield f"Error: {str(e)}"
        return

    logger.info("=" * 80)
    logger.info(f"Streaming Complete - Request ID: {request_id}")
    logger.info("=" * 80)


if __name__ == "__main__":
    # Run with AgentCore wrapper
    app.run()
