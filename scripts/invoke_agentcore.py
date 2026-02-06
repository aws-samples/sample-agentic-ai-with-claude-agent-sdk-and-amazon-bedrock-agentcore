#!/usr/bin/env python3
"""
Interactive AgentCore Invoker with Multi-Round Clarification Support

This script wraps AgentCore invocations to handle multiple rounds of clarification
questions automatically. It continuously loops, collecting user answers and
re-invoking the agent until no more clarification is needed.

Features:
- Automatic detection of AskUserQuestion tool usage
- Multi-round clarification handling (as many rounds as needed)
- Session preservation across all rounds
- Clean terminal UI with progress indicators

Usage:
    # Local dev mode
    python scripts/invoke_agentcore.py --dev "How many students are enrolled?"

    # AWS hosted mode
    python scripts/invoke_agentcore.py "How many students are enrolled?"
"""

import argparse
import json
import subprocess
import sys
import re
import uuid


def extract_claude_sdk_session_id(output: str) -> str | None:
    """
    Extract Claude Agent SDK Session ID from AgentCore structured JSON output.

    Args:
        output: Full output from AgentCore invocation

    Returns:
        Session ID string or None if not found
    """
    # Primary method: Extract from structured JSON blocks (more reliable)
    try:
        # Find JSON blocks in the output (AgentCore yields JSON for structured data)
        json_matches = re.findall(r'```json\s*(\{.*?\})\s*```', output, re.DOTALL)
        for json_str in json_matches:
            try:
                data = json.loads(json_str)
                # Check for claude_agent_sdk_session_id in the structured output
                if 'claude_agent_sdk_session_id' in data and data['claude_agent_sdk_session_id']:
                    return data['claude_agent_sdk_session_id']
            except json.JSONDecodeError:
                continue
    except Exception as e:
        pass

    return None


def parse_clarification_questions(output: str) -> list[dict] | None:
    """
    Parse clarification questions from AgentCore output (JSON format only).

    Extracts structured JSON questions from AskUserQuestion tool output.

    Args:
        output: Full output from AgentCore invocation

    Returns:
        List of question dicts with 'question', 'header', 'options', and 'multiSelect',
        or None if no clarification needed
    """
    try:
        # Extract structured JSON questions from output
        json_matches = re.findall(r'```json\s*(\{.*?\})\s*```', output, re.DOTALL)
        for json_str in json_matches:
            try:
                data = json.loads(json_str)
                if data.get('status') == 'clarification_needed' and 'questions' in data:
                    # Convert structured questions to the format expected by collect_user_answers
                    questions = []
                    for q in data['questions']:
                        # Convert options from {label, description} to display strings
                        options = []
                        for i, opt in enumerate(q.get('options', []), 1):
                            options.append(f"{i}. {opt['label']} - {opt['description']}")

                        questions.append({
                            'question': q.get('question', ''),
                            'header': q.get('header', ''),
                            'options': options,
                            'multiSelect': q.get('multiSelect', False)
                        })
                    return questions if questions else None
            except json.JSONDecodeError:
                continue
    except Exception as e:
        pass

    return None


def collect_user_answers(questions: list[dict]) -> tuple[str, str]:
    """
    Interactively collect user answers to clarification questions.

    Args:
        questions: List of question dicts from parse_clarification_questions
                  Each dict has: 'question', 'options', optional 'header', optional 'multiSelect'

    Returns:
        Tuple of (answers_only, questions_and_answers) where:
        - answers_only: Formatted string with just the answers (for display)
        - questions_and_answers: Formatted string with both questions and answers (for follow-up query)
    """
    print("\n" + "=" * 80)
    print("📋 CLARIFICATION NEEDED")
    print("=" * 80)
    print("\nPlease answer the following questions:\n")

    answers_only = []
    questions_and_answers = []

    for i, q_data in enumerate(questions, 1):
        question = q_data['question']
        options = q_data['options']
        header = q_data.get('header', '')
        multi_select = q_data.get('multiSelect', False)

        # Display question with header if available
        display_question = f"{header}: {question}" if header else question
        print(f"\n{display_question}")

        for opt in options:
            print(f"  {opt}")

        # Show input hint based on multi-select
        if multi_select:
            print("  (Enter numbers separated by commas, or type your own answer)")
        else:
            print("  (Enter a number, or type your own answer)")

        while True:
            answer = input(f"\nYour choice: ").strip()

            if not answer:
                print("❌ Please provide an answer.")
                continue

            # Check if it's number(s) (option selection)
            if all(c.isdigit() or c == ',' or c.isspace() for c in answer):
                try:
                    # Parse comma-separated numbers
                    indices = [int(s.strip()) for s in answer.split(",") if s.strip()]
                    valid_selections = []

                    for idx in indices:
                        if 1 <= idx <= len(options):
                            valid_selections.append(options[idx - 1])
                        else:
                            print(f"❌ Invalid option: {idx}. Please enter numbers between 1 and {len(options)}.")
                            valid_selections = []
                            break

                    if valid_selections:
                        if multi_select:
                            answer_text = ', '.join(valid_selections)
                            answers_only.append(f"Q{i}: {answer_text}")
                            questions_and_answers.append(f"Q{i}: {display_question}\nA{i}: {answer_text}")
                        else:
                            if len(valid_selections) > 1:
                                print("❌ This question allows only one selection.")
                                continue
                            answer_text = valid_selections[0]
                            answers_only.append(f"Q{i}: {answer_text}")
                            questions_and_answers.append(f"Q{i}: {display_question}\nA{i}: {answer_text}")
                        break
                except ValueError:
                    # User typed their own answer
                    answers_only.append(f"Q{i}: {answer}")
                    questions_and_answers.append(f"Q{i}: {display_question}\nA{i}: {answer}")
                    break
            else:
                # User typed their own answer
                answers_only.append(f"Q{i}: {answer}")
                questions_and_answers.append(f"Q{i}: {display_question}\nA{i}: {answer}")
                break

    return "\n".join(answers_only), "\n\n".join(questions_and_answers)


def invoke_agentcore(query: str, session_id: str, dev_mode: bool = False, claude_sdk_session_id: str = None, agent_name: str = None) -> tuple[str, bool]:
    """
    Invoke AgentCore with a query and stream output in real-time.

    Args:
        query: The query to send to AgentCore
        session_id: AgentCore session ID for tracking invocations
        dev_mode: Whether to use local dev mode (--dev flag)
        claude_sdk_session_id: Optional Claude Agent SDK Session ID to resume
        agent_name: Optional agent name to invoke (from .bedrock_agentcore.yaml)

    Returns:
        Tuple of (output_text, is_error)
    """
    # Build the command
    cmd = ["agentcore", "invoke"]

    if dev_mode:
        cmd.append("--dev")

    # Add agent name if specified
    if agent_name:
        cmd.extend(["--agent", agent_name])

    # Add session ID
    cmd.extend(["--session-id", session_id])

    # Build the payload
    payload = {"query": query}
    if claude_sdk_session_id:
        payload["claude_agent_sdk_session_id"] = claude_sdk_session_id

    cmd.append(json.dumps(payload))

    # Show the actual command being executed
    print("\n" + "─" * 80)
    print(f"🚀 Invoking AgentCore ({'dev mode' if dev_mode else 'AWS hosted'})...")
    print("─" * 80)
    print(f"📋 Command: {' '.join(cmd)}")
    if claude_sdk_session_id:
        print(f"🔄 Resuming Claude SDK Session: {claude_sdk_session_id}")
    print("─" * 80)

    try:
        # Use Popen to stream output in real-time
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,  # Combine stderr with stdout
            text=True,
            bufsize=1,  # Line buffered
            universal_newlines=True
        )

        # Collect output while streaming
        output_lines = []

        print("\n📡 Streaming output:\n")

        # Read and display output line by line
        for line in process.stdout:
            # Display immediately (streaming)
            print(line, end='', flush=True)
            # Also collect for parsing
            output_lines.append(line)

        # Wait for process to complete
        return_code = process.wait(timeout=300)  # 5 minute timeout

        # Combine all output
        full_output = ''.join(output_lines)

        return full_output, return_code != 0

    except subprocess.TimeoutExpired:
        process.kill()
        return "❌ Error: AgentCore invocation timed out after 5 minutes", True
    except FileNotFoundError:
        return "❌ Error: 'agentcore' command not found. Make sure AgentCore is installed.", True
    except Exception as e:
        return f"❌ Error invoking AgentCore: {str(e)}", True


def main():
    """Main entry point for the interactive AgentCore invoker."""
    parser = argparse.ArgumentParser(
        description='Interactive AgentCore invoker with multi-round clarification handling',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Examples:
  # Local dev mode with automatic multi-round clarification
  python scripts/invoke_agentcore.py --dev "How many students are enrolled?"

  # AWS hosted mode (supports multiple rounds automatically)
  python scripts/invoke_agentcore.py "Show me enrollment trends"

  # Specific agent (use follow-up agent with clarification support)
  python scripts/invoke_agentcore.py --dev --agent student_analytics_agent_followup "Show me the top students"

  # Specific query (may need multiple rounds of clarification)
  python scripts/invoke_agentcore.py --dev "Analyze student performance by department"

Note: The script automatically handles multiple rounds of clarification questions.
      It will continue to ask and collect answers until the agent has all needed information.
        '''
    )

    parser.add_argument(
        'query',
        nargs='*',
        help='Natural language query to send to AgentCore'
    )

    parser.add_argument(
        '--dev',
        action='store_true',
        help='Use local dev mode (agentcore invoke --dev)'
    )

    parser.add_argument(
        '--agent',
        type=str,
        default=None,
        help='Agent name to invoke (from .bedrock_agentcore.yaml)'
    )

    args = parser.parse_args()

    # Get query from arguments
    if not args.query:
        print("❌ Error: No query provided.")
        print("\nUsage: python scripts/invoke_agentcore.py [--dev] \"<your query>\"")
        sys.exit(1)

    user_query = " ".join(args.query)

    # Generate AgentCore session ID for this invocation
    agentcore_session_id = str(uuid.uuid4())

    print("=" * 80)
    print("AGENTCORE INTERACTIVE INVOKER")
    print("=" * 80)
    print(f"Mode: {'Local Dev' if args.dev else 'AWS Hosted'}")
    if args.agent:
        print(f"Agent: {args.agent}")
    print(f"AgentCore Session ID: {agentcore_session_id}")
    print(f"Query: {user_query}")
    print("=" * 80)

    # Track session and rounds
    claude_sdk_session_id = None
    current_query = user_query
    round_number = 0

    # Loop to handle multiple rounds of clarification
    while True:
        round_number += 1

        if round_number == 1:
            print(f"\n🚀 Starting initial invocation...")
        else:
            print(f"\n🔄 Round {round_number} invocation...")

        # Invoke AgentCore
        output, is_error = invoke_agentcore(
            current_query,
            agentcore_session_id,
            args.dev,
            claude_sdk_session_id=claude_sdk_session_id,
            agent_name=args.agent
        )

        if is_error:
            print(f"\n❌ Invocation failed at round {round_number}:")
            print(output)
            sys.exit(1)

        # Extract Claude Agent SDK Session ID (preserve across rounds)
        session_id = extract_claude_sdk_session_id(output)
        if session_id:
            claude_sdk_session_id = session_id

        # Check if clarification is needed
        questions = parse_clarification_questions(output)

        if questions is None:
            # No more clarification needed - we're done!
            print("\n" + "=" * 80)
            if round_number == 1:
                print("✓ COMPLETE (No clarification needed)")
            else:
                print(f"✓ COMPLETE (After {round_number - 1} round(s) of clarification)")
            if claude_sdk_session_id:
                print(f"Claude Agent SDK Session ID: {claude_sdk_session_id}")
            print("=" * 80)
            sys.exit(0)

        # Clarification is needed
        print("\n" + "=" * 80)
        print(f"🔍 CLARIFICATION DETECTED (Round {round_number})")
        print("=" * 80)

        # Log Claude Agent SDK Session ID
        if claude_sdk_session_id:
            print(f"\n📋 Claude Agent SDK Session ID: {claude_sdk_session_id}")
            print(f"[INFO] Session will be preserved for next round")
        else:
            print("\n⚠️  Warning: Could not extract Claude Agent SDK Session ID from output")

        # Collect user answers interactively
        try:
            answers_display, questions_and_answers = collect_user_answers(questions)
        except KeyboardInterrupt:
            print("\n\n❌ Cancelled by user.")
            sys.exit(1)

        print("\n" + "=" * 80)
        print(f"✓ Answers collected for round {round_number}:")
        print("=" * 80)
        for line in answers_display.split('\n'):
            print(f"  {line}")

        # Build follow-up query with both questions and answers

        follow_up_query = f"""My answers to your clarification questions:

{questions_and_answers}

Now proceed with the analysis using these parameters."""

        print("\n" + "=" * 80)
        print(f"📝 FOLLOW-UP QUERY (Round {round_number})")
        print("=" * 80)
        print(follow_up_query)

        if claude_sdk_session_id:
            print("\n" + "─" * 80)
            print(f"🔄 Resuming Claude Agent SDK Session: {claude_sdk_session_id}")
            print("─" * 80)

        # Update current_query for next iteration
        current_query = follow_up_query

        # Loop will continue to next round if more clarification is needed


if __name__ == "__main__":
    main()
