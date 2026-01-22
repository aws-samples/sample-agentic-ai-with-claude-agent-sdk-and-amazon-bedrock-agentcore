#!/usr/bin/env python3
"""
Observable Student Analytics Agent - WITH OpenTelemetry Instrumentation.

This agent extends skills_agent.py from Module 1 with:
- GenAI semantic convention spans for CloudWatch GenAI Observability
- Session context for trace correlation
- Cost and performance metrics
- Tool call tracking with child spans
- MCP tool for Athena queries

Key features for CloudWatch GenAI Observability:
- Uses tracer scope recognized by CloudWatch (openinference.instrumentation.*)
- GenAI semantic convention attributes (gen_ai.operation.name, gen_ai.agent.name, etc.)
- Proper events with gen_ai.event.name structure

To run with observability:
  opentelemetry-instrument python agent/skills_agent_observable.py --session-id demo-001 "Your query"
"""

import os
import sys
import json
import uuid
import argparse
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Also load observability env if exists
obs_env = Path(__file__).parent.parent / ".env.observability"
if obs_env.exists():
    load_dotenv(obs_env)

# Add parent directory to path to import tools
sys.path.insert(0, str(Path(__file__).parent.parent))

from claude_agent_sdk import tool, create_sdk_mcp_server, ClaudeAgentOptions, ClaudeSDKClient
from tools.athena_tools import AthenaQueryExecutor

# OpenTelemetry imports - graceful degradation if not available
try:
    from opentelemetry import trace, baggage, context
    from opentelemetry.trace import Status, StatusCode, SpanKind
    OTEL_AVAILABLE = True
except ImportError:
    OTEL_AVAILABLE = False
    trace = None

# Try to import OpenInference instrumentation for Bedrock (auto-instruments Bedrock calls)
try:
    from openinference.instrumentation.bedrock import BedrockInstrumentor
    OPENINFERENCE_AVAILABLE = True
    # Instrument Bedrock client for automatic span creation
    BedrockInstrumentor().instrument()
except ImportError:
    OPENINFERENCE_AVAILABLE = False

# Agent identification constants - GenAI semantic convention attributes
AGENT_NAME = "student-analytics-agent"
AGENT_VERSION = "1.0.0"
AGENT_DESCRIPTION = "Student Analytics AI Agent for querying student management data"


def print_sql_box(sql: str):
    """Print SQL query with delimiters."""
    print("\n" + "-" * 50)
    print("SQL QUERY")
    print("-" * 50)
    print(sql)
    print("-" * 50)


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


async def run_observable_agent(user_query: str, debug_mode: bool = False, session_id: str = None):
    """
    Run the enhanced student analytics agent with GenAI semantic convention observability.

    Uses tracer scope 'openinference.instrumentation.claude_agent_sdk' for CloudWatch
    GenAI Observability compatibility.

    Args:
        user_query: Natural language question from the user
        debug_mode: Whether to show debug information
        session_id: Optional session ID for trace correlation
    """
    # Generate unique request ID for this query
    request_id = str(uuid.uuid4())

    # Generate session ID if not provided
    if session_id is None:
        session_id = f"session-{uuid.uuid4().hex[:8]}"

    # Set up OpenTelemetry tracer if available and enabled
    tracer = None
    session_span = None
    context_token = None

    if OTEL_AVAILABLE and os.getenv("AGENT_OBSERVABILITY_ENABLED") == "true":
        # Use strands.telemetry.tracer scope which is recognized by CloudWatch GenAI Observability
        # This scope is used by AWS Strands SDK and is the only custom scope that properly appears in aws/spans
        tracer = trace.get_tracer(
            "strands.telemetry.tracer",
            AGENT_VERSION
        )
        # Set session context in baggage for correlation
        ctx = baggage.set_baggage("session.id", session_id)
        context_token = context.attach(ctx)
        print(f"[Observability] Session: {session_id}")
        if OPENINFERENCE_AVAILABLE:
            print(f"[Observability] OpenInference Bedrock instrumentation: enabled")

    # Load project context from CLAUDE.md
    project_root = Path(__file__).parent.parent
    claude_md_path = project_root / "CLAUDE.md"

    if not claude_md_path.exists():
        print("Warning: CLAUDE.md not found. Agent will work with limited context.")
        project_context = ""
    else:
        with open(claude_md_path, 'r') as f:
            project_context = f.read()
        print(f"Loaded project context from CLAUDE.md ({len(project_context)} chars)")

    # Get configuration from environment
    athena_database = os.getenv("ATHENA_DATABASE", "student_analytics")
    athena_output = os.getenv("ATHENA_OUTPUT_LOCATION", "s3://your-bucket/athena-results/")
    aws_region = os.getenv("AWS_REGION", "us-east-1")

    # Ensure processed results directory exists with request_id subdirectory
    processed_dir = project_root / "results" / "processed" / request_id
    processed_dir.mkdir(parents=True, exist_ok=True)

    # Initialize Athena executor with configuration
    athena_executor = AthenaQueryExecutor(
        database=athena_database,
        output_location=athena_output,
        results_dir=f"./results/raw/{request_id}",
        region=aws_region
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

            return {
                "content": [
                    {"type": "text", "text": str(result)}
                ]
            }

        except Exception as e:
            return {
                "content": [
                    {"type": "text", "text": f"Error executing query: {str(e)}"}
                ],
                "isError": True
            }

    # Create SDK MCP server
    athena_server = create_sdk_mcp_server(
        name="athena",
        version="1.0.0",
        tools=[execute_athena_query]
    )

    # Configure options with full context
    options = ClaudeAgentOptions(
        system_prompt=f"""You are a Student Analytics AI Agent helping users analyze student management data through natural language queries.

IMPORTANT: This request has ID: {request_id}
- All processed files (visualizations, reports, analysis) must be saved to: results/processed/{request_id}/
- Query results are automatically saved to: results/raw/{request_id}/ by the execute_athena_query tool

{project_context}
""",
        mcp_servers={"athena": athena_server},
        allowed_tools=["Skill", "Read", "Write", "Bash", "mcp__athena__execute_athena_query"],
        setting_sources=["project"],  # Enable skill discovery from .claude/skills/
        cwd=str(project_root),
        max_turns=30
    )

    print("=" * 80)
    print("OBSERVABLE STUDENT ANALYTICS AGENT (With OpenTelemetry)")
    print("=" * 80)
    print(f"Request ID: {request_id}")
    print(f"\nUser Query: {user_query}\n")
    print("-" * 80)

    # Track metrics for observability
    tool_calls = []
    skills_loaded = []
    response_text = ""
    input_tokens = 0
    output_tokens = 0

    # Available tools list for span attributes
    available_tools = ["Skill", "Read", "Write", "Bash", "mcp__athena__execute_athena_query"]

    # Create the main agent span if observability is enabled
    span_context_manager = None
    if tracer:
        # Use GenAI semantic convention span name: "invoke_agent {agent_name}"
        span_context_manager = tracer.start_as_current_span(
            f"invoke_agent {AGENT_NAME}",
            kind=SpanKind.INTERNAL
        )
        session_span = span_context_manager.__enter__()

        # Set GenAI semantic convention attributes
        span_attrs = create_agent_span_attributes(
            session_id, request_id, user_query, available_tools
        )
        for key, value in span_attrs.items():
            session_span.set_attribute(key, value)

        # Add input event with GenAI semantic convention structure
        session_span.add_event("gen_ai.user.message", {
            "gen_ai.event.name": "user_message",
            "session.id": session_id,
            "content": user_query[:1000]
        })

    try:
        # Use ClaudeSDKClient
        async with ClaudeSDKClient(options=options) as client:
            await client.query(user_query)

            async for message in client.receive_response():
                if debug_mode:
                    print("\n[DEBUG] Message structure:")
                    print("-" * 40)
                    try:
                        if hasattr(message, 'model_dump'):
                            print(json.dumps(message.model_dump(), indent=2, default=str))
                        elif hasattr(message, '__dict__'):
                            print(json.dumps(message.__dict__, indent=2, default=str))
                        else:
                            print(repr(message))
                    except Exception as e:
                        print(f"Could not serialize: {e}")
                    print("-" * 40)

                # Handle system messages
                if hasattr(message, 'subtype'):
                    if message.subtype == 'init':
                        if debug_mode:
                            print("[System initialized]")
                        continue
                    elif message.subtype == 'success':
                        duration_ms = getattr(message, 'duration_ms', 0)
                        duration_s = duration_ms / 1000
                        cost = getattr(message, 'total_cost_usd', 0)
                        turns = getattr(message, 'num_turns', 0)

                        # Extract token counts if available
                        input_tokens = getattr(message, 'input_tokens', input_tokens)
                        output_tokens = getattr(message, 'output_tokens', output_tokens)

                        print("\n" + "=" * 80)
                        print("Analysis Complete")
                        print(f"Duration: {duration_s:.1f}s | Cost: ${cost:.4f} | Turns: {turns}")
                        print("=" * 80)

                        # Set completion metrics with GenAI semantic conventions
                        if session_span:
                            # GenAI semantic convention token attributes
                            session_span.set_attribute("gen_ai.usage.input_tokens", input_tokens)
                            session_span.set_attribute("gen_ai.usage.output_tokens", output_tokens)
                            session_span.set_attribute("gen_ai.usage.total_tokens", input_tokens + output_tokens)

                            # Agent-specific metrics
                            session_span.set_attribute("agent.duration_ms", duration_ms)
                            session_span.set_attribute("agent.cost_usd", cost)
                            session_span.set_attribute("agent.num_turns", turns)
                            session_span.set_attribute("agent.response_length", len(response_text))
                            session_span.set_attribute("agent.tool_calls_count", len(tool_calls))
                            session_span.set_attribute("agent.skills_loaded", json.dumps(skills_loaded))
                            session_span.set_attribute("agent.tools_used", json.dumps(list(set(tool_calls))))

                            # Add completion event with GenAI semantic convention
                            session_span.add_event("gen_ai.agent.finish", {
                                "gen_ai.event.name": "agent_finish",
                                "session.id": session_id,
                                "success": True,
                                "duration_ms": duration_ms,
                                "cost_usd": cost,
                                "num_turns": turns,
                                "tool_calls_count": len(tool_calls)
                            })
                            session_span.set_status(Status(StatusCode.OK))
                        continue

                # Handle messages with content
                if hasattr(message, 'content'):
                    content_list = message.content if isinstance(message.content, list) else [message.content]

                    for content in content_list:
                        # Text content
                        if hasattr(content, 'text'):
                            text = content.text
                            response_text += text
                            if text.startswith("Base directory for this skill"):
                                print(text.split('\n', 1)[0])
                            else:
                                print(text)

                            # Add assistant message event with GenAI semantic convention
                            if session_span:
                                session_span.add_event("gen_ai.assistant.message", {
                                    "gen_ai.event.name": "assistant_message",
                                    "session.id": session_id,
                                    "content_preview": text[:500]
                                })

                        # Tool use - show tool invocations and create spans
                        elif hasattr(content, 'name') and hasattr(content, 'input'):
                            tool_name = content.name
                            tool_calls.append(tool_name)

                            # Create child span for tool call with GenAI semantic conventions
                            if tracer:
                                with tracer.start_as_current_span(
                                    f"execute_tool {tool_name}",
                                    kind=SpanKind.INTERNAL
                                ) as tool_span:
                                    # Set GenAI semantic convention tool attributes
                                    tool_attrs = create_tool_span_attributes(
                                        tool_name, len(tool_calls), session_id
                                    )
                                    for key, value in tool_attrs.items():
                                        tool_span.set_attribute(key, value)

                                    if tool_name == "Skill":
                                        skill_name = content.input.get('skill', 'unknown')
                                        skills_loaded.append(skill_name)
                                        tool_span.set_attribute("skill.name", skill_name)
                                        tool_span.add_event("skill_loaded", {
                                            "skill": skill_name,
                                            "session.id": session_id
                                        })
                                        print(f"\n[Loading skill: {skill_name}]")

                                    elif tool_name == "Read":
                                        file_path = content.input.get('file_path', '')
                                        tool_span.set_attribute("file.path", file_path)
                                        if 'metadata' in file_path and debug_mode:
                                            print(f"\n[Reading metadata: {Path(file_path).name}]")

                                    elif tool_name == "mcp__athena__execute_athena_query":
                                        query_sql = content.input.get('query', '')
                                        filename = content.input.get('local_filename', '')
                                        tool_span.set_attribute("db.statement", query_sql[:500])
                                        tool_span.set_attribute("db.system", "athena")
                                        tool_span.set_attribute("athena.output_file", filename)
                                        tool_span.add_event("sql_query_submitted", {
                                            "sql_preview": query_sql[:200],
                                            "session.id": session_id
                                        })
                                        print(f"\ninvoking tool: {tool_name}")
                                        print_sql_box(query_sql)
                                        print(f"\nSaving to: {filename}")
                                        print("Executing query...")

                                    elif tool_name == "Write":
                                        file_path = content.input.get('file_path', '')
                                        tool_span.set_attribute("file.path", file_path)

                                    elif debug_mode:
                                        print(f"\n[Tool: {tool_name}]")

                                    tool_span.set_status(Status(StatusCode.OK))
                            else:
                                # No observability - original behavior
                                if tool_name == "Skill":
                                    skill_name = content.input.get('skill', 'unknown')
                                    skills_loaded.append(skill_name)
                                    print(f"\n[Loading skill: {skill_name}]")
                                elif tool_name == "mcp__athena__execute_athena_query":
                                    query_sql = content.input.get('query', '')
                                    filename = content.input.get('local_filename', '')
                                    print(f"\ninvoking tool: {tool_name}")
                                    print_sql_box(query_sql)
                                    print(f"\nSaving to: {filename}")
                                    print("Executing query...")
                                elif debug_mode:
                                    print(f"\n[Tool: {tool_name}]")

                        # Tool results
                        elif hasattr(content, 'tool_use_id') and hasattr(content, 'content'):
                            result_str = str(content.content)
                            if "Query completed successfully!" in result_str or "'local_file':" in result_str:
                                print("\nQuery completed successfully!")

    except Exception as e:
        # Record error in span with GenAI semantic convention
        if session_span:
            session_span.set_attribute("error.message", str(e))
            session_span.set_attribute("error.type", type(e).__name__)
            session_span.add_event("gen_ai.agent.error", {
                "gen_ai.event.name": "agent_error",
                "session.id": session_id,
                "error.message": str(e),
                "error.type": type(e).__name__
            })
            session_span.set_status(Status(StatusCode.ERROR, str(e)))
        raise
    finally:
        # Close the span
        if span_context_manager:
            span_context_manager.__exit__(None, None, None)

        # Force flush spans to ensure they are exported
        if OTEL_AVAILABLE:
            try:
                provider = trace.get_tracer_provider()
                if hasattr(provider, 'force_flush'):
                    provider.force_flush(timeout_millis=30000)
                    print("[Observability] Force flushed spans to exporter")
            except Exception as e:
                print(f"[Observability] Warning: Failed to force flush spans: {e}")

        # Detach context
        if context_token:
            context.detach(context_token)


def main():
    """Main entry point with argument parsing."""
    parser = argparse.ArgumentParser(
        description='Observable Student Analytics Agent (With OpenTelemetry)',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Examples:
  python agent/skills_agent_observable.py "How many students are enrolled?"
  python agent/skills_agent_observable.py --session-id user-123 "Show me the top 10 students by GPA"

With observability:
  opentelemetry-instrument python agent/skills_agent_observable.py "Your query"
  opentelemetry-instrument python agent/skills_agent_observable.py --session-id demo-001 "Your query"
        '''
    )

    parser.add_argument(
        'query',
        nargs='*',
        help='Natural language query about student data'
    )

    parser.add_argument(
        '--debug',
        action='store_true',
        help='Enable debug mode'
    )

    parser.add_argument(
        '--session-id',
        type=str,
        default=None,
        help='Session ID for trace correlation (auto-generated if not provided)'
    )

    args = parser.parse_args()

    if args.query:
        user_query = " ".join(args.query)
    else:
        user_query = "How many students are currently enrolled?"

    import anyio
    anyio.run(run_observable_agent, user_query, args.debug, args.session_id)


if __name__ == "__main__":
    main()
