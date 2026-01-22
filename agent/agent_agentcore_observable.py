#!/usr/bin/env python3
"""
Observable Student Analytics AI Agent with Amazon Bedrock AgentCore wrapper.
This version extends agent_agentcore.py with OpenTelemetry instrumentation
following GenAI semantic conventions for CloudWatch GenAI Observability.

Key features:
- GenAI semantic convention attributes for proper CloudWatch visualization
- Automatic Bedrock instrumentation via OpenInference
- Custom spans for agent workflow tracking
- Events with proper input/output structure

For Module 3b: AgentCore Deployment with Observability
"""

import os
import sys
import json
import uuid
import logging
import time
from pathlib import Path
from urllib.parse import urlparse
import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

# Configure logging for CloudWatch
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    force=True
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

# OpenTelemetry imports - graceful degradation if not available
try:
    from opentelemetry import trace, baggage, context
    from opentelemetry.trace import Status, StatusCode, SpanKind
    OTEL_AVAILABLE = True
    logger.info("OpenTelemetry is available - observability enabled")
except ImportError:
    OTEL_AVAILABLE = False
    trace = None
    logger.warning("OpenTelemetry not available - observability disabled")

# Try to import OpenInference instrumentation for Bedrock
try:
    from openinference.instrumentation.bedrock import BedrockInstrumentor
    OPENINFERENCE_AVAILABLE = True
    # Instrument Bedrock client for automatic span creation
    BedrockInstrumentor().instrument()
    logger.info("OpenInference Bedrock instrumentation enabled")
except ImportError:
    OPENINFERENCE_AVAILABLE = False
    logger.info("OpenInference not available - using manual instrumentation only")

# Agent identification constants - GenAI semantic convention attributes
AGENT_NAME = "student-analytics-agent"
AGENT_VERSION = "1.0.0"
AGENT_DESCRIPTION = "Student Analytics AI Agent for querying student management data"

# Initialize AgentCore app
app = BedrockAgentCoreApp()

# Get environment configuration
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
        logger.info(f"Generated SigV4 signed URL for s3://{bucket}/{s3_key}")
        return url
    except ClientError as e:
        logger.error(f"Failed to generate signed URL: {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error generating signed URL: {e}")
        return None


def create_agent_span_attributes(session_id: str, request_id: str, user_query: str, tools: list) -> dict:
    """
    Create GenAI semantic convention attributes for agent spans.

    Reference: https://opentelemetry.io/docs/specs/semconv/gen-ai/gen-ai-agent-spans/
    Uses strands-agents format for CloudWatch GenAI Observability compatibility.
    """
    return {
        # Required GenAI semantic convention attributes
        "gen_ai.operation.name": "invoke_agent",
        "gen_ai.system": "strands-agents",  # Use strands-agents for CloudWatch compatibility
        "gen_ai.agent.name": AGENT_NAME,

        # Session tracking (required for CloudWatch correlation)
        "session.id": session_id,

        # Agent metadata
        "agent.name": AGENT_NAME,
        "agent.version": AGENT_VERSION,
        "agent.description": AGENT_DESCRIPTION,
        "agent.request_id": request_id,

        # Query info
        "gen_ai.prompt": user_query[:500],
        "agent.query_length": len(user_query),

        # Tool definitions
        "gen_ai.agent.tools": json.dumps(tools),
    }


def create_tool_span_attributes(tool_name: str, sequence: int, session_id: str) -> dict:
    """Create GenAI semantic convention attributes for tool spans."""
    return {
        "gen_ai.operation.name": "execute_tool",
        "gen_ai.tool.name": tool_name,
        "tool.name": tool_name,
        "tool.sequence": sequence,
        "session.id": session_id,
    }


@app.entrypoint
async def main(payload: dict = None):
    """
    Main entrypoint for AgentCore with streaming support and observability.
    Uses GenAI semantic conventions for CloudWatch GenAI Observability.
    """
    # Generate unique IDs
    request_id = str(uuid.uuid4())
    start_time = time.time()

    # Get session ID from AgentCore runtime or generate one
    session_id = os.getenv("BEDROCK_AGENTCORE_SESSION_ID", str(uuid.uuid4()))

    # Extract user query from payload
    if payload is None or "query" not in payload:
        yield {
            "error": "Missing 'query' field in payload",
            "example": {"query": "How many students are currently enrolled?"}
        }
        return

    user_query = payload["query"]

    # Set up OpenTelemetry tracer and session context
    tracer = None
    ctx_token = None

    if OTEL_AVAILABLE:
        # Get tracer - use strands.telemetry.tracer scope which is recognized by CloudWatch GenAI Observability
        # This scope is used by AWS Strands SDK and is the only custom scope that properly appears in aws/spans
        tracer = trace.get_tracer(
            "strands.telemetry.tracer",
            AGENT_VERSION
        )

        # Set session ID in baggage for downstream propagation
        ctx = baggage.set_baggage("session.id", session_id)
        ctx_token = context.attach(ctx)

        parent_span = trace.get_current_span()
        parent_context = parent_span.get_span_context() if parent_span else None

        if parent_context and parent_context.is_valid:
            logger.info(f"[Observability] Parent trace_id: {format(parent_context.trace_id, '032x')}, session_id: {session_id}")
        else:
            logger.info(f"[Observability] New trace, session_id: {session_id}")

    # Load project context from CLAUDE.md
    project_root = Path(__file__).parent.parent
    claude_md_path = project_root / "CLAUDE.md"

    if not claude_md_path.exists():
        logger.warning("CLAUDE.md not found.")
        project_context = ""
    else:
        with open(claude_md_path, 'r') as f:
            project_context = f.read()
        logger.info(f"Loaded project context ({len(project_context)} chars)")

    # Initialize Athena executor
    athena_executor = AthenaQueryExecutor(
        database=ATHENA_DATABASE,
        output_location=ATHENA_OUTPUT,
        results_dir=f"./results/raw/{request_id}",
        region=AWS_REGION
    )

    # Define the Athena query tool
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
                "content": [{"type": "text", "text": response_text}]
            }

        except Exception as e:
            return {
                "content": [{"type": "text", "text": f"Error executing query: {str(e)}"}],
                "isError": True
            }

    # Create MCP server with the Athena tool
    athena_server = create_sdk_mcp_server(
        name="athena",
        version="1.0.0",
        tools=[execute_athena_query]
    )

    # Available tools list for span attributes
    available_tools = ["Skill", "Read", "Write", "Bash", "mcp__athena__execute_athena_query"]

    # Configure agent options
    options = ClaudeAgentOptions(
        system_prompt=f"""You are a Student Analytics AI Agent running on Amazon Bedrock AgentCore.

IMPORTANT: This request has ID: {request_id}
- All processed files must be saved to: results/processed/{request_id}/
- Query results are automatically saved to: results/raw/{request_id}/

{project_context}
""",
        allowed_tools=available_tools,
        mcp_servers={"athena": athena_server},
        setting_sources=["project"],
        cwd=str(project_root),
        max_turns=30
    )

    logger.info("=" * 80)
    logger.info("OBSERVABLE STUDENT ANALYTICS AI AGENT (AgentCore + GenAI Observability)")
    logger.info(f"Request ID: {request_id}")
    logger.info(f"Session ID: {session_id}")
    logger.info("=" * 80)
    logger.info(f"User Query: {user_query}")
    logger.info("-" * 80)

    # Ensure results directories exist
    processed_dir = project_root / "results" / "processed" / request_id
    processed_dir.mkdir(parents=True, exist_ok=True)
    raw_dir = project_root / "results" / "raw" / request_id

    # Parse S3 bucket
    s3_bucket = parse_s3_bucket_from_output_location(ATHENA_OUTPUT)

    # Track metrics
    tool_calls = []
    skills_loaded = []
    response_text = ""
    input_tokens = 0
    output_tokens = 0

    # Run the agent with observability
    try:
        if tracer:
            # Create agent invocation span with GenAI semantic conventions
            with tracer.start_as_current_span(
                f"invoke_agent {AGENT_NAME}",
                kind=SpanKind.INTERNAL
            ) as agent_span:

                # Set GenAI semantic convention attributes
                span_attrs = create_agent_span_attributes(
                    session_id, request_id, user_query, available_tools
                )
                for key, value in span_attrs.items():
                    agent_span.set_attribute(key, value)

                # Add input event with proper structure
                agent_span.add_event("gen_ai.user.message", {
                    "gen_ai.event.name": "user_message",
                    "session.id": session_id,
                    "content": user_query[:1000]
                })

                logger.info(f"[Observability] Created invoke_agent span")

                async with ClaudeSDKClient(options=options) as client:
                    await client.query(user_query)

                    async for message in client.receive_response():
                        result = await process_message_with_observability(
                            message, tracer, agent_span, session_id,
                            tool_calls, skills_loaded, response_text,
                            input_tokens, output_tokens
                        )

                        if result.get("yield_content"):
                            yield result["yield_content"]

                        response_text = result.get("response_text", response_text)
                        tool_calls = result.get("tool_calls", tool_calls)
                        skills_loaded = result.get("skills_loaded", skills_loaded)
                        input_tokens = result.get("input_tokens", input_tokens)
                        output_tokens = result.get("output_tokens", output_tokens)

                        if result.get("completion_metrics"):
                            metrics = result["completion_metrics"]
                            duration_ms = metrics["duration_ms"]
                            cost = metrics["cost"]
                            turns = metrics["turns"]

                            # Set completion metrics with GenAI semantic conventions
                            agent_span.set_attribute("gen_ai.usage.input_tokens", input_tokens)
                            agent_span.set_attribute("gen_ai.usage.output_tokens", output_tokens)
                            agent_span.set_attribute("gen_ai.usage.total_tokens", input_tokens + output_tokens)
                            agent_span.set_attribute("agent.cost_usd", cost)
                            agent_span.set_attribute("agent.num_turns", turns)
                            agent_span.set_attribute("agent.duration_ms", duration_ms)
                            agent_span.set_attribute("agent.tool_calls_count", len(tool_calls))
                            agent_span.set_attribute("agent.skills_loaded", json.dumps(skills_loaded))

                            # Add completion event
                            agent_span.add_event("gen_ai.agent.finish", {
                                "gen_ai.event.name": "agent_finish",
                                "session.id": session_id,
                                "success": True,
                                "duration_ms": duration_ms,
                                "cost_usd": cost,
                                "num_turns": turns,
                                "tool_calls_count": len(tool_calls)
                            })

                            agent_span.set_status(Status(StatusCode.OK))

                # Upload files after completion
                files_output = await handle_file_uploads(processed_dir, raw_dir, s3_bucket, request_id)
                if files_output:
                    yield files_output

        else:
            # No observability - run without spans
            async with ClaudeSDKClient(options=options) as client:
                await client.query(user_query)

                async for message in client.receive_response():
                    result = process_message_simple(message, tool_calls, skills_loaded, response_text)
                    if result.get("yield_content"):
                        yield result["yield_content"]
                    response_text = result.get("response_text", response_text)
                    tool_calls = result.get("tool_calls", tool_calls)
                    skills_loaded = result.get("skills_loaded", skills_loaded)

            # Upload files
            files_output = await handle_file_uploads(processed_dir, raw_dir, s3_bucket, request_id)
            if files_output:
                yield files_output

    except Exception as e:
        logger.error("=" * 80)
        logger.error("ERROR DURING AGENT EXECUTION")
        logger.error(f"Request ID: {request_id}")
        logger.error(f"Error: {str(e)}")
        import traceback
        logger.error(f"Traceback:\n{traceback.format_exc()}")
        logger.error("=" * 80)

        if tracer:
            current_span = trace.get_current_span()
            if current_span and current_span.is_recording():
                current_span.set_attribute("error.message", str(e))
                current_span.set_attribute("error.type", type(e).__name__)
                current_span.add_event("gen_ai.agent.error", {
                    "gen_ai.event.name": "agent_error",
                    "session.id": session_id,
                    "error.message": str(e),
                    "error.type": type(e).__name__
                })
                current_span.set_status(Status(StatusCode.ERROR, str(e)))

        yield f"Error: {str(e)}"
        return

    finally:
        # Force flush spans to ensure they are exported before container shutdown
        if OTEL_AVAILABLE:
            try:
                from opentelemetry.sdk.trace import TracerProvider
                provider = trace.get_tracer_provider()
                if hasattr(provider, 'force_flush'):
                    provider.force_flush(timeout_millis=30000)
                    logger.info("[Observability] Force flushed spans to exporter")
            except Exception as e:
                logger.warning(f"[Observability] Failed to force flush spans: {e}")

        # Detach context
        if ctx_token:
            context.detach(ctx_token)

    logger.info("=" * 80)
    logger.info(f"Streaming Complete - Request ID: {request_id}")
    logger.info("=" * 80)


async def process_message_with_observability(
    message, tracer, parent_span, session_id,
    tool_calls, skills_loaded, response_text,
    input_tokens, output_tokens
):
    """Process agent message with GenAI semantic convention observability."""
    result = {
        "yield_content": None,
        "response_text": response_text,
        "tool_calls": tool_calls,
        "skills_loaded": skills_loaded,
        "completion_metrics": None,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens
    }

    if hasattr(message, 'subtype'):
        if message.subtype == 'init':
            logger.info("[SYSTEM] Agent initialized")
        elif message.subtype == 'success':
            duration_ms = getattr(message, 'duration_ms', 0)
            cost = getattr(message, 'total_cost_usd', 0)
            turns = getattr(message, 'num_turns', 0)

            # Extract token counts if available
            result["input_tokens"] = getattr(message, 'input_tokens', input_tokens)
            result["output_tokens"] = getattr(message, 'output_tokens', output_tokens)

            logger.info(f"Analysis Complete - Duration: {duration_ms/1000:.1f}s | Cost: ${cost:.4f} | Turns: {turns}")
            result["completion_metrics"] = {
                "duration_ms": duration_ms,
                "cost": cost,
                "turns": turns
            }

    if hasattr(message, 'content'):
        content_list = message.content if isinstance(message.content, list) else [message.content]

        for block in content_list:
            if hasattr(block, 'text'):
                result["response_text"] += block.text
                if block.text.startswith("Base directory for this skill"):
                    first_line = block.text.split('\n', 1)[0]
                    result["yield_content"] = '\n' + first_line + '\n'
                else:
                    result["yield_content"] = '\n' + block.text + '\n'

                # Add assistant message event
                parent_span.add_event("gen_ai.assistant.message", {
                    "gen_ai.event.name": "assistant_message",
                    "session.id": session_id,
                    "content_preview": block.text[:500]
                })

            elif hasattr(block, 'name') and hasattr(block, 'input'):
                tool_name = block.name
                result["tool_calls"].append(tool_name)
                logger.info(f"[TOOL USE] {tool_name}")

                # Create tool span with GenAI semantic conventions
                with tracer.start_as_current_span(
                    f"execute_tool {tool_name}",
                    kind=SpanKind.INTERNAL
                ) as tool_span:

                    tool_attrs = create_tool_span_attributes(
                        tool_name, len(result["tool_calls"]), session_id
                    )
                    for key, value in tool_attrs.items():
                        tool_span.set_attribute(key, value)

                    if tool_name == "Skill":
                        skill_name = block.input.get('skill', 'unknown')
                        result["skills_loaded"].append(skill_name)
                        tool_span.set_attribute("skill.name", skill_name)
                        tool_span.add_event("skill_loaded", {
                            "skill": skill_name,
                            "session.id": session_id
                        })
                        result["yield_content"] = f"\n🎯 Loading skill: {skill_name}\n"

                    elif tool_name == "mcp__athena__execute_athena_query":
                        query_sql = block.input.get('query', '')
                        filename = block.input.get('local_filename', '')
                        tool_span.set_attribute("db.statement", query_sql[:500])
                        tool_span.set_attribute("db.system", "athena")
                        tool_span.set_attribute("athena.output_file", filename)
                        tool_span.add_event("sql_query_submitted", {
                            "sql_preview": query_sql[:200],
                            "session.id": session_id
                        })

                        sql_output = f"\ninvoking tool: {tool_name}\n"
                        if query_sql:
                            sql_output += f"\n{'─' * 50}\n📊 SQL QUERY\n{'─' * 50}\n{query_sql}\n{'─' * 50}\n\n💾 Saving to: {filename}\n\n⏳ Executing query...\n"
                        result["yield_content"] = sql_output

                    elif tool_name == "Read":
                        file_path = block.input.get('file_path', '')
                        tool_span.set_attribute("file.path", file_path)

                    elif tool_name == "Write":
                        file_path = block.input.get('file_path', '')
                        tool_span.set_attribute("file.path", file_path)

                    tool_span.set_status(Status(StatusCode.OK))

            elif hasattr(block, 'tool_use_id') and hasattr(block, 'content'):
                is_error = getattr(block, 'is_error', False)
                logger.info(f"[TOOL RESULT] Error: {is_error}")

    return result


def process_message_simple(message, tool_calls, skills_loaded, response_text):
    """Process agent message without observability."""
    result = {
        "yield_content": None,
        "response_text": response_text,
        "tool_calls": tool_calls,
        "skills_loaded": skills_loaded
    }

    if hasattr(message, 'subtype'):
        if message.subtype == 'init':
            logger.info("[SYSTEM] Agent initialized")
        elif message.subtype == 'success':
            duration_s = getattr(message, 'duration_ms', 0) / 1000
            cost = getattr(message, 'total_cost_usd', 0)
            turns = getattr(message, 'num_turns', 0)
            logger.info(f"Analysis Complete - Duration: {duration_s:.1f}s | Cost: ${cost:.4f} | Turns: {turns}")

    if hasattr(message, 'content'):
        content_list = message.content if isinstance(message.content, list) else [message.content]

        for block in content_list:
            if hasattr(block, 'text'):
                result["response_text"] += block.text
                if block.text.startswith("Base directory for this skill"):
                    first_line = block.text.split('\n', 1)[0]
                    result["yield_content"] = '\n' + first_line + '\n'
                else:
                    result["yield_content"] = '\n' + block.text + '\n'

            elif hasattr(block, 'name') and hasattr(block, 'input'):
                tool_name = block.name
                result["tool_calls"].append(tool_name)

                if tool_name == "Skill":
                    skill_name = block.input.get('skill', 'unknown')
                    result["skills_loaded"].append(skill_name)
                    result["yield_content"] = f"\n🎯 Loading skill: {skill_name}\n"

                elif tool_name == "mcp__athena__execute_athena_query":
                    query_sql = block.input.get('query', '')
                    filename = block.input.get('local_filename', '')

                    sql_output = f"\ninvoking tool: {tool_name}\n"
                    if query_sql:
                        sql_output += f"\n{'─' * 50}\n📊 SQL QUERY\n{'─' * 50}\n{query_sql}\n{'─' * 50}\n\n💾 Saving to: {filename}\n\n⏳ Executing query...\n"
                    result["yield_content"] = sql_output

    return result


async def handle_file_uploads(processed_dir, raw_dir, s3_bucket, request_id):
    """Handle file uploads to S3 after agent completion."""
    processed_files = list(processed_dir.glob("*"))
    raw_files = list(raw_dir.glob("*")) if raw_dir.exists() else []

    total_files = len([f for f in processed_files if f.is_file()]) + len([f for f in raw_files if f.is_file()])

    if total_files > 0 and s3_bucket:
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
            return f"\n\n```json\n{json.dumps(output, indent=2)}\n```\n"

    return None


if __name__ == "__main__":
    app.run()
