#!/usr/bin/env python3
"""
Enhanced Student Analytics Agent - WITH Skills and Project Context.

This agent demonstrates the full power of the Claude Agent SDK with:
- Domain-specific skills (enrollment, academic, financial)
- Project context from CLAUDE.md
- Structured workflows and best practices
- MCP tool for Athena queries

Compare this with basic_agent.py to see the difference skills make!
"""

import os
import sys
import json
import argparse
import logging
import uuid
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Suppress verbose Claude Agent SDK output
logging.getLogger("claude_agent_sdk").setLevel(logging.WARNING)

# Add parent directory to path to import tools
sys.path.insert(0, str(Path(__file__).parent.parent))

from claude_agent_sdk import tool, create_sdk_mcp_server, ClaudeAgentOptions, ClaudeSDKClient
from tools.athena_tools import AthenaQueryExecutor


def display_tool_use(content, debug_mode=False, request_id=None):
    """Display tool use message."""
    if debug_mode:
        print("\n[DEBUG] ToolUseBlock:")
        print(f"  Tool: {content.name}")
        print(f"  ID: {content.id}")
        print(f"  Input: {json.dumps(content.input, indent=2, default=str)}")
        return

    # Display Skill tool invocations
    if content.name == "Skill":
        skill_name = content.input.get('skill', 'unknown')
        print(f"\n🎯 Loading skill: {skill_name}")
        return

    # For execute_athena_query tool
    if content.name == "mcp__athena__execute_athena_query":
        print()
        print(f"invoking tool: {content.name}")
        filename = content.input.get('local_filename', '')


def display_tool_result(content, debug_mode=False):
    """Display tool result message."""
    if debug_mode:
        print("\n[DEBUG] ToolResultBlock:")
        print(f"  Tool Use ID: {content.tool_use_id}")
        print(f"  Is Error: {content.is_error}")
        print(f"  Content: {content.content[:200]}..." if len(str(content.content)) > 200 else f"  Content: {content.content}")
        return

    if content.is_error:
        print("\n✗ Error occurred:")
        print(f"  {str(content.content)[:200]}")


def display_text_message(text: str, debug_mode=False):
    """Display text message from assistant."""
    if debug_mode:
        print(f"\n[DEBUG] TextBlock: {text}")
    else:
        print()
        if text.startswith("Base directory for this skill"):
            # Only yield the first line (before the first \n) with newline at the end
            first_line = text.split('\n', 1)[0]
            print(first_line)
        else:
            print(text)


def display_summary(message, debug_mode=False):
    """Display summary message."""
    if hasattr(message, 'subtype') and message.subtype == 'success':
        duration_s = getattr(message, 'duration_ms', 0) / 1000
        cost = getattr(message, 'total_cost_usd', 0)
        turns = getattr(message, 'num_turns', 0)

        if not debug_mode:
            print("\n" + "=" * 80)
            print("Analysis Complete")
            if cost and turns:
                print(f"Model Cost: ${cost:.2f} | Duration: {duration_s:.1f}s | Turns: {turns}")
            print("=" * 80)
        else:
            print(f"\n[DEBUG] ResultMessage:")
            print(f"  Duration: {duration_s:.1f}s")
            print(f"  Model Cost: ${cost:.2f}")
            print(f"  Turns: {turns}")
            print(f"  Usage: {json.dumps(getattr(message, 'usage', {}), indent=2, default=str)}")


async def run_skills_agent(user_query: str, debug_mode: bool = False):
    """
    Run the enhanced student analytics agent with skills and context.

    Args:
        user_query: Natural language question from the user
        debug_mode: Whether to show debug information
    """
    # Generate unique request ID for this query
    request_id = str(uuid.uuid4())

    # Load project context from CLAUDE.md
    project_root = Path(__file__).parent.parent
    claude_md_path = project_root / "CLAUDE.md"

    if not claude_md_path.exists():
        print("Warning: CLAUDE.md not found. Agent will work with limited context.")
        project_context = ""
    else:
        with open(claude_md_path, 'r') as f:
            project_context = f.read()

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
    print("ENHANCED STUDENT ANALYTICS AGENT (With Skills & Context)")
    print("=" * 80)
    print(f"Request ID: {request_id}")
    print(f"\nUser Query: {user_query}\n")
    print("-" * 80)

    # Track skills loaded for display
    skills_loaded = []

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
                        print(f"\n[DEBUG] System initialized")
                    continue
                elif message.subtype == 'success':
                    display_summary(message, debug_mode)
                    continue

            # Handle messages with content
            if hasattr(message, 'content'):
                content_list = message.content if isinstance(message.content, list) else [message.content]

                for content in content_list:
                    # TextBlock - agent's text responses
                    if hasattr(content, 'text'):
                        display_text_message(content.text, debug_mode)

                    # ToolUseBlock - tool executions
                    elif hasattr(content, 'name') and hasattr(content, 'input'):
                        # Track skills
                        if content.name == "Skill":
                            skill_name = content.input.get('skill', 'unknown')
                            skills_loaded.append(skill_name)
                        display_tool_use(content, debug_mode, request_id)

                    # ToolResultBlock - tool results
                    elif hasattr(content, 'tool_use_id') and hasattr(content, 'content'):
                        display_tool_result(content, debug_mode)

                    # Unknown content type
                    elif debug_mode:
                        print(f"\n[DEBUG] Unknown content type: {type(content)}")


def main():
    """Main entry point with argument parsing."""
    parser = argparse.ArgumentParser(
        description='Enhanced Student Analytics Agent (With Skills)',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Examples:
  python agent/skills_agent.py "How many students are enrolled?"
  python agent/skills_agent.py "Show me the top 10 students by GPA"
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
    anyio.run(run_skills_agent, user_query, args.debug)


if __name__ == "__main__":
    main()
