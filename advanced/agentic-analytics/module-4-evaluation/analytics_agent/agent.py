"""
Agentic Analytics Agent — text-to-SQL over Amazon Athena.

This is the SINGLE SOURCE OF TRUTH for the agent's identity. Both the local
`run_query()` path (Module 1) and the AgentCore entrypoint (Module 2+) call
`build_agent_options()`, so the system prompt, tools, MCP server, and
filesystem settings are defined in exactly one place.

Later modules override defaults rather than forking:
  - Module 2 (deploy): the thin entrypoint calls build_agent_options() as-is.
  - Module 3 (follow-up): passes enable_clarification=True to add the
    AskUserQuestion tool — no forked agent file.
"""
from __future__ import annotations

import json
import os
import uuid
from collections.abc import Callable
from typing import Any, Literal

from dotenv import load_dotenv

from claude_agent_sdk import (
    ClaudeAgentOptions,
    ClaudeSDKClient,
    create_sdk_mcp_server,
    tool,
)

load_dotenv()

# The agent's working directory — the bundle root. CLAUDE.md, .claude/ (skills),
# and data/metadata all live here and are loaded from disk via setting_sources.
AGENT_DIR = os.path.dirname(os.path.abspath(__file__))

# The agent's identity. The CLAUDE.md in this bundle carries the detailed
# workflow (load a skill → read table metadata → write SQL → run it → analyze);
# this prompt is the always-on framing. Per-request file-routing is appended by
# build_agent_options() so outputs land under results/<request_id>/.
SYSTEM_PROMPT = """You are a Student Analytics AI Agent. You answer natural-language
questions about a university's student data by writing SQL, running it on Amazon Athena
via the execute_athena_query tool, and analyzing the results.

Only SELECT queries are allowed. Follow the workflow in CLAUDE.md: load the right skill,
read the table metadata first, then write SQL using exact column names."""

CLARIFICATION_PROMPT = """

When a question is ambiguous AFTER you've loaded the relevant skill, use the
AskUserQuestion tool to ask 2-4 clear options BEFORE writing any SQL. Do not guess."""


def _default_output_location() -> str:
    """Derive the Athena results location from the account id (Module 0's bucket).

    Lets both local runs and the deployed runtime work without anyone hardcoding
    an account-specific bucket in config. Override with ATHENA_OUTPUT_LOCATION.
    """
    explicit = os.getenv("ATHENA_OUTPUT_LOCATION")
    if explicit:
        return explicit
    import boto3

    account = boto3.client("sts").get_caller_identity()["Account"]
    return f"s3://student-analytics-agent-{account}/athena-results/"


def _athena_executor(request_id: str):
    """Build the AthenaQueryExecutor from environment config (per request)."""
    from tools.athena_tools import AthenaQueryExecutor

    return AthenaQueryExecutor(
        database=os.getenv("ATHENA_DATABASE", "student_analytics"),
        output_location=_default_output_location(),
        results_dir=f"./results/raw/{request_id}",
        region=os.getenv("AWS_REGION", "us-west-2"),
    )


def _make_athena_server(request_id: str):
    """Create the in-process MCP server exposing the execute_athena_query tool.

    The AthenaQueryExecutor (and its STS/boto3 calls) is built lazily on first tool
    use, NOT at construction time — so build_agent_options() stays a pure, no-AWS
    call that the fast tests can exercise without credentials.
    """
    executor_holder: dict = {}

    def _get_executor():
        if "executor" not in executor_holder:
            executor_holder["executor"] = _athena_executor(request_id)
        return executor_holder["executor"]

    @tool(
        "execute_athena_query",
        "Execute a SQL SELECT query on Amazon Athena and download the results to a CSV.",
        {"query": str, "local_filename": str},
    )
    async def execute_athena_query(args: dict) -> dict:
        try:
            result = _get_executor().execute_and_download(
                query=args.get("query", ""),
                local_filename=args.get("local_filename", "query_results.csv"),
            )
            text = (
                "Query completed.\n"
                f"Data scanned: {result.get('data_scanned_bytes', 0) / 1024**2:.2f} MB\n"
                f"Execution time: {result.get('execution_time_ms', 0) / 1000:.2f}s\n"
                f"Results saved to: {result['local_file']}"
            )
            return {"content": [{"type": "text", "text": text}]}
        except Exception as e:  # surfaced back to the model as a tool error
            return {"content": [{"type": "text", "text": f"Error executing query: {e}"}],
                    "isError": True}

    return create_sdk_mcp_server(name="athena", version="1.0.0", tools=[execute_athena_query])


def build_agent_options(
    request_id: str | None = None,
    *,
    enable_clarification: bool = False,
    extra_tools: list[str] | None = None,
    can_use_tool: Callable | None = None,
    **overrides: Any,
) -> ClaudeAgentOptions:
    """Build the agent's ClaudeAgentOptions — the single source of truth.

    Args:
        request_id: groups this run's output files under results/<request_id>/.
            A fresh uuid is generated if omitted.
        enable_clarification: add the AskUserQuestion tool + clarification prompt
            (Module 3). Off by default.
        extra_tools: append extra allowed-tool names.
        can_use_tool: optional permission callback (Module 3 uses it for
            AskUserQuestion handling).
        **overrides: override any ClaudeAgentOptions field (e.g. max_turns=50).

    No model= is set — the model comes from ANTHROPIC_MODEL with
    CLAUDE_CODE_USE_BEDROCK=1.
    """
    request_id = request_id or str(uuid.uuid4())
    athena_server = _make_athena_server(request_id)

    tools = ["Skill", "Read", "Write", "Bash", "mcp__athena__execute_athena_query"]
    system_prompt = SYSTEM_PROMPT
    if enable_clarification:
        tools.append("AskUserQuestion")
        system_prompt += CLARIFICATION_PROMPT
    if extra_tools:
        tools = tools + extra_tools

    system_prompt += (
        f"\n\nThis request's id is {request_id}. Save any files you create "
        f"(processed data, charts, reports) under results/processed/{request_id}/."
    )

    defaults: dict[str, Any] = dict(
        system_prompt=system_prompt,
        allowed_tools=tools,
        mcp_servers={"athena": athena_server},
        # setting_sources=["project"] loads filesystem settings from cwd: CLAUDE.md,
        # skills (.claude/skills), subagents, slash commands, hooks. Without it the
        # SDK runs in isolation mode and the skills/CLAUDE.md are NOT loaded.
        setting_sources=["project"],
        cwd=AGENT_DIR,
        max_turns=30,
    )
    if can_use_tool is not None:
        defaults["can_use_tool"] = can_use_tool
    defaults.update(overrides)
    return ClaudeAgentOptions(**defaults)


async def run_query(
    user_query: str,
    *,
    request_id: str | None = None,
    activity_handler: Callable[[Any], None] | None = None,
    **option_overrides: Any,
) -> tuple[str | None, list]:
    """Run a natural-language query against the local agent.

    Returns (final_text, messages). Streams activity via activity_handler if given.
    """
    options = build_agent_options(request_id=request_id, **option_overrides)

    result: str | None = None
    messages: list = []
    async with ClaudeSDKClient(options=options) as client:
        await client.query(user_query)
        async for msg in client.receive_response():
            messages.append(msg)
            if activity_handler:
                activity_handler(msg)
            if hasattr(msg, "result"):
                result = msg.result
    return result, messages
