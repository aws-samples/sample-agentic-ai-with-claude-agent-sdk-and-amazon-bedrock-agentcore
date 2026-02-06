#!/usr/bin/env python3
"""
Student Analytics AI Agent with Follow-up Questions Support.

This agent demonstrates how to handle ambiguous user queries by:
- Using the AskUserQuestion tool for structured clarification
- Collecting and processing user responses interactively
- Continuing with the analysis using clarified parameters

Based on the Claude Agent SDK with AskUserQuestion tool pattern.
"""

import os
import sys
import re
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
from claude_agent_sdk.types import (
    HookMatcher,
    PermissionResultAllow,
    PermissionResultDeny,
    ToolPermissionContext,
)
from tools.athena_tools import AthenaQueryExecutor


def display_tool_use(content, debug_mode=False, request_id=None):
    """
    Display tool use message.

    Args:
        content: ToolUseBlock content
        debug_mode: Whether to show debug information
        request_id: Request ID for displaying file paths
    """
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

    # Display AskUserQuestion tool - clarification questions
    if content.name == "AskUserQuestion":
        num_questions = len(content.input.get('questions', []))
        print(f"\n❓ Claude is asking {num_questions} clarification question(s)...")
        return

    # For execute_athena_query tool, extract and display SQL
    if content.name == "mcp__athena__execute_athena_query":
        print()
        print(f"invoking tool: {content.name}")
        filename = content.input.get('local_filename', '')


def display_tool_result(content, debug_mode=False):
    """
    Display tool result message.

    Args:
        content: ToolResultBlock content
        debug_mode: Whether to show debug information
    """
    if debug_mode:
        print("\n[DEBUG] ToolResultBlock:")
        print(f"  Tool Use ID: {content.tool_use_id}")
        print(f"  Is Error: {content.is_error}")
        print(f"  Content: {content.content[:200]}..." if len(str(content.content)) > 200 else f"  Content: {content.content}")
        return

    # Parse execution metrics from Athena tool output
    result_str = str(content.content)

    if content.is_error:
        print("\n✗ Error occurred:")
        print(f"  {result_str}")


def display_text_message(text: str, debug_mode=False):
    """
    Display text message from assistant.

    Args:
        text: Text content
        debug_mode: Whether to show debug information
    """
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
    """
    Display summary message.

    Args:
        message: ResultMessage
        debug_mode: Whether to show debug information
    """
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


def parse_user_response(response: str, options: list) -> str:
    """
    Parse user input as option number(s) or free text.

    Args:
        response: User input (e.g., "1", "1,2", or "my custom answer")
        options: List of option dictionaries with 'label' and 'description' fields

    Returns:
        Selected option label(s) joined with ", " or the free text input
    """
    response = response.strip()
    if not response:
        return ""

    try:
        # Try to parse as comma-separated numbers
        indices = [int(s.strip()) - 1 for s in response.split(",")]
        labels = [options[i]["label"] for i in indices if 0 <= i < len(options)]
        return ", ".join(labels) if labels else response
    except ValueError:
        # Not a number, treat as free text
        return response


async def handle_ask_user_question(input_data: dict) -> PermissionResultAllow:
    """
    Display Claude's clarification questions and collect user answers.

    This follows the official Claude Agent SDK pattern for handling AskUserQuestion tool.

    Args:
        input_data: Dictionary containing 'questions' array from Claude

    Returns:
        PermissionResultAllow with the original questions and collected answers
    """
    print("\n" + "─" * 80)
    print("📋 Claude needs clarification:")
    print("─" * 80)

    answers = {}

    for q in input_data.get("questions", []):
        print(f"\n{q['header']}: {q['question']}")

        options = q["options"]
        for i, opt in enumerate(options):
            print(f"  {i + 1}. {opt['label']} - {opt['description']}")

        if q.get("multiSelect"):
            print("  (Enter numbers separated by commas, or type your own answer)")
        else:
            print("  (Enter a number, or type your own answer)")

        response = input("Your choice: ").strip()
        answers[q["question"]] = parse_user_response(response, options)

    print("─" * 80)

    return PermissionResultAllow(
        updated_input={
            "questions": input_data.get("questions", []),
            "answers": answers,
        }
    )


async def run_followup_agent(user_query: str, debug_mode: bool = False):
    """
    Run the student analytics agent with a user query.

    Args:
        user_query: Natural language question from the user
        debug_mode: Whether to show debug information
    """
    # Generate unique request ID for this query
    request_id = str(uuid.uuid4())

    # Define the can_use_tool callback for handling permissions and clarification questions
    async def can_use_tool(
        tool_name: str, input_data: dict, context: ToolPermissionContext
    ) -> PermissionResultAllow | PermissionResultDeny:
        """Handle tool permission requests and clarification questions."""

        # Handle AskUserQuestion tool - Claude asking for clarification
        if tool_name == "AskUserQuestion":
            return await handle_ask_user_question(input_data)

        # Auto-approve all other tools (Read, Write, Bash, execute_athena_query)
        # This matches the current behavior of permission_mode="acceptEdits"
        return PermissionResultAllow(updated_input=input_data)

    # a hook required for Python streaming mode to keep stream open for can_use_tool
    async def can_use_tool_hook(input_data, tool_use_id, context):
        return {"continue_": True}

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
    # Pass full path with request_id included
    athena_executor = AthenaQueryExecutor(
        database=athena_database,
        output_location=athena_output,
        results_dir=f"./results/raw/{request_id}",
        region=aws_region
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

    # Configure options
    options = ClaudeAgentOptions(
        system_prompt=f"""You are a Student Analytics AI Agent helping users analyze student management data through natural language queries.

IMPORTANT: This request has ID: {request_id}
- All processed files (visualizations, reports, analysis) must be saved to: results/processed/{request_id}/
- Query results are automatically saved to: results/raw/{request_id}/ by the execute_athena_query tool

{project_context}

**CRITICAL - Query Clarification Protocol:**
When a user query is ambiguous or could be interpreted multiple ways AFTER loading skills, you should ask for clarification BEFORE creating and executing any SQL query.

To ask clarification questions:
1. Use the AskUserQuestion tool to present your questions to the user
2. Provide 2-4 clear options for each question with descriptive labels
3. DO NOT execute any queries until you receive the user's answers
4. After receiving answers, re-evaluate what skill is the best to proceed with the user query

""",
        mcp_servers={"athena": athena_server},
        allowed_tools=["Skill", "Read", "Write", "Bash", "AskUserQuestion", "mcp__athena__execute_athena_query"],
        can_use_tool=can_use_tool,
        hooks={"PreToolUse": [HookMatcher(matcher=None, hooks=[can_use_tool_hook])]},
        permission_mode="acceptEdits",  # Auto-accept edits, no permission prompts
        setting_sources=["project"],
        cwd=str(project_root),
        max_turns=30
    )

    print("=" * 80)
    print("STUDENT ANALYTICS AI AGENT")
    print("=" * 80)
    print(f"Request ID: {request_id}")
    print(f"\nUser Query: {user_query}\n")
    print("─" * 80)

    # Use ClaudeSDKClient to execute the query
    async with ClaudeSDKClient(options=options) as client:
        await client.query(user_query)

        # Process response stream
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
                    print(f"Could not serialize to JSON: {e}")
                    print(f"Type: {type(message)}")
                print("-" * 40)

            # Handle different message types
            # Check if it's a system message (init/success/error)
            if hasattr(message, 'subtype'):
                if message.subtype == 'init':
                    session_id = getattr(message, 'session_id', None) or getattr(message, 'data', {}).get('session_id', 'N/A')
                    print(f"Claude Agent SDK Session ID: {session_id}")
                    if debug_mode:
                        print(f"\n[DEBUG] System initialized - Session: {getattr(message, 'data', {}).get('session_id', 'N/A')}")
                        print(f"Full message: {message}")
                    continue
                elif message.subtype == 'success':
                    display_summary(message, debug_mode)
                    return
                elif message.subtype == 'error':
                    print(f"\n✗ Task failed: {getattr(message, 'result', 'Unknown error')}")
                    return

            # Handle messages with content
            if hasattr(message, 'content'):
                content_list = message.content if isinstance(message.content, list) else [message.content]

                for content in content_list:
                    # TextBlock - agent's text responses
                    if hasattr(content, 'text'):
                        display_text_message(content.text, debug_mode)

                    # ToolUseBlock - tool executions
                    elif hasattr(content, 'name') and hasattr(content, 'input'):
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
        description='Student Analytics AI Agent - Query student management data using natural language',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Examples:
  python module-4-improve-agentic-workflow/followup_agent.py "How many students are enrolled?"
  python module-4-improve-agentic-workflow/followup_agent.py "Show me the top 10 students by GPA"
  python module-4-improve-agentic-workflow/followup_agent.py --debug "What's the average GPA by department?"
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
        help='Enable debug mode to show detailed message structures'
    )

    args = parser.parse_args()

    # Get query from arguments or use default
    if args.query:
        user_query = " ".join(args.query)
    else:
        user_query = "How many students are currently enrolled?"

    # Run the agent
    import anyio
    anyio.run(run_followup_agent, user_query, args.debug)


if __name__ == "__main__":
    main()
