#!/usr/bin/env python3
"""
Basic Student Analytics Agent - WITHOUT Skills or Project Context.

This is a minimal agent that demonstrates the Claude Agent SDK without
any skills or CLAUDE.md context. It will work but may struggle with:
- Knowing exact column names
- Understanding table structure
- Following best practices for queries

This is intentionally limited to demonstrate the value of skills/context.
"""

import os
import sys
import json
import argparse
import uuid
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Add parent directory to path to import tools
sys.path.insert(0, str(Path(__file__).parent.parent))

from claude_agent_sdk import tool, create_sdk_mcp_server, ClaudeAgentOptions, ClaudeSDKClient
from tools.athena_tools import AthenaQueryExecutor


def display_tool_use(content, debug_mode=False):
    """Display tool use message."""
    if debug_mode:
        print(f"\n[DEBUG] Tool: {content.name}")
        print(f"  Input: {json.dumps(content.input, indent=2, default=str)}")
        return

    if content.name == "mcp__athena__execute_athena_query":
        print(f"\ninvoking tool: {content.name}")


def display_tool_result(content, debug_mode=False):
    """Display tool result message."""
    if debug_mode:
        print(f"\n[DEBUG] Tool Result (error={content.is_error})")
        return

    if content.is_error:
        print(f"\n✗ Error: {str(content.content)[:200]}")


def display_text_message(text: str, debug_mode=False):
    """Display text message from assistant."""
    if debug_mode:
        print(f"\n[DEBUG] Text: {text[:100]}...")
    else:
        print()
        print(text)


def display_summary(message, debug_mode=False):
    """Display summary message."""
    if hasattr(message, 'subtype') and message.subtype == 'success':
        duration_s = getattr(message, 'duration_ms', 0) / 1000
        cost = getattr(message, 'total_cost_usd', 0)
        turns = getattr(message, 'num_turns', 0)

        print("\n" + "=" * 80)
        print("Analysis Complete")
        if cost and turns:
            print(f"Model Cost: ${cost:.2f} | Duration: {duration_s:.1f}s | Turns: {turns}")
        print("=" * 80)


async def run_basic_agent(user_query: str, debug_mode: bool = False):
    """
    Run the basic student analytics agent with minimal context.

    Args:
        user_query: Natural language question from the user
        debug_mode: Whether to show debug information
    """
    # Generate unique request ID for this query
    request_id = str(uuid.uuid4())

    # Get configuration from environment
    athena_database = os.getenv("ATHENA_DATABASE", "student_analytics")
    athena_output = os.getenv("ATHENA_OUTPUT_LOCATION", "s3://your-bucket/athena-results/")
    aws_region = os.getenv("AWS_REGION", "us-east-1")

    project_root = Path(__file__).parent.parent

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

    # Minimal system prompt - no skills, no detailed context
    system_prompt = f"""You are a Student Analytics AI Agent. Your role is to help users
analyze student management data through natural language queries.

IMPORTANT: This request has ID: {request_id}
- All processed files (visualizations, reports, analysis) must be saved to: results/processed/{request_id}/
- Query results are automatically saved to: results/raw/{request_id}/ by the execute_athena_query tool

You have access to an Amazon Athena database with student data.

Database: {athena_database}
Region: {aws_region}

Use the execute_athena_query tool to run SQL queries. It takes two parameters:
- query: The SQL query string
- local_filename: A descriptive filename for the results (e.g., "enrollment_count.csv")

Available tables (approximate - you may need to explore):
- student_enrollment_analytics
- student_academic_performance
- financial_summary_by_student
- course_performance_analytics
- instructor_performance_summary
- department_summary_metrics

Note: You'll need to figure out the exact column names by querying the tables.
Only SELECT queries are allowed for security.
"""

    # Configure agent options - with Athena MCP tool but no skills
    options = ClaudeAgentOptions(
        system_prompt=system_prompt,
        mcp_servers={"athena": athena_server},
        allowed_tools=["Read", "Write", "Bash", "mcp__athena__execute_athena_query"],  # No Skill tool
        # No setting_sources - no skills discovery
        cwd=str(project_root),
        max_turns=20
    )

    print("=" * 80)
    print("BASIC STUDENT ANALYTICS AGENT (No Skills/Context)")
    print("=" * 80)
    print(f"Request ID: {request_id}")
    print(f"\nUser Query: {user_query}\n")
    print("-" * 80)

    # Use ClaudeSDKClient
    async with ClaudeSDKClient(options=options) as client:
        await client.query(user_query)

        async for message in client.receive_response():
            # Handle system messages
            if hasattr(message, 'subtype'):
                if message.subtype == 'init':
                    continue
                elif message.subtype == 'success':
                    display_summary(message, debug_mode)
                    continue

            # Handle messages with content
            if hasattr(message, 'content'):
                content_list = message.content if isinstance(message.content, list) else [message.content]

                for content in content_list:
                    if hasattr(content, 'text'):
                        display_text_message(content.text, debug_mode)
                    elif hasattr(content, 'name') and hasattr(content, 'input'):
                        display_tool_use(content, debug_mode)
                    elif hasattr(content, 'tool_use_id') and hasattr(content, 'content'):
                        display_tool_result(content, debug_mode)


def main():
    """Main entry point with argument parsing."""
    parser = argparse.ArgumentParser(
        description='Basic Student Analytics Agent (No Skills)',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Examples:
  python agent/basic_agent.py "How many students are enrolled?"
  python agent/basic_agent.py "Show me the top 10 students by GPA"
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

    args = parser.parse_args()

    if args.query:
        user_query = " ".join(args.query)
    else:
        user_query = "How many students are currently enrolled?"

    import anyio
    anyio.run(run_basic_agent, user_query, args.debug)


if __name__ == "__main__":
    main()
