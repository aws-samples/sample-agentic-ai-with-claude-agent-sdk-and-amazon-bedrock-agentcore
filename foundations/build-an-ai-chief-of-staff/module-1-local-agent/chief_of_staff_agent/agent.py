"""
Chief of Staff Agent
"""

import asyncio
import json
import os
from collections.abc import Callable
from typing import Any, Literal

from dotenv import load_dotenv

from claude_agent_sdk import ClaudeAgentOptions, ClaudeSDKClient

load_dotenv()


# The agent's "identity" — the single source of truth, shared by the local
# send_query() path (Module 1) and the AgentCore entrypoint (Module 2+).
SYSTEM_PROMPT = """You are the Chief of Staff for TechStart Inc, a 50-person startup.

        Apart from your tools and two subagents, you also have custom Python scripts in the scripts/ directory you can run with Bash:
        - python scripts/financial_forecast.py: Advanced financial modeling
        - python scripts/talent_scorer.py: Candidate scoring algorithm
        - python scripts/decision_matrix.py: Strategic decision framework

        You have access to company data in the financial_data/ directory.
        """

# The agent's working directory — the bundle root (CLAUDE.md, .claude/, scripts/,
# financial_data/ all live here and are loaded from disk via setting_sources).
AGENT_DIR = os.path.dirname(os.path.abspath(__file__))


def build_agent_options(
    *,
    continue_conversation: bool = False,
    permission_mode: Literal["default", "plan", "acceptEdits"] = "default",
    output_style: str | None = None,
    extra_tools: list[str] | None = None,
    system_prompt_suffix: str | None = None,
    **overrides: Any,
) -> ClaudeAgentOptions:
    """Build the agent's ClaudeAgentOptions — the single source of truth.

    Both the local ``send_query()`` and the AgentCore entrypoint call this, so the
    agent's identity (system prompt, tools, cwd, setting_sources) is defined in one
    place. Later modules override defaults rather than forking:

    - ``extra_tools``: append tools (e.g. Module 3 memory tools).
    - ``system_prompt_suffix``: append text to the system prompt (e.g. Module 3
      injects recalled memory here) without replacing the canonical prompt — keeps
      prompt assembly inside this single source of truth.
    - ``**overrides``: override any ClaudeAgentOptions field (e.g. ``max_turns=50``).

    No ``model=`` is set — this workshop runs on Amazon Bedrock and the model comes
    from the ``ANTHROPIC_MODEL`` env var (with ``CLAUDE_CODE_USE_BEDROCK=1``).
    """
    tools = ["Task", "Read", "Write", "Edit", "Bash", "WebSearch"]
    if extra_tools:
        tools = tools + extra_tools

    system_prompt = SYSTEM_PROMPT + (system_prompt_suffix or "")

    defaults: dict[str, Any] = dict(
        allowed_tools=tools,
        system_prompt=system_prompt,
        continue_conversation=continue_conversation,
        permission_mode=permission_mode,
        cwd=AGENT_DIR,
        settings=json.dumps({"outputStyle": output_style}) if output_style else None,
        # IMPORTANT: setting_sources must include "project" to load filesystem settings:
        # CLAUDE.md, skills (.claude/skills), subagents (.claude/agents), slash
        # commands (.claude/commands), output styles, and hooks (.claude/settings.json).
        # Without this, the SDK runs in isolation mode with no filesystem settings.
        setting_sources=["project"],
    )
    defaults.update(overrides)  # callers override any field
    return ClaudeAgentOptions(**defaults)


def get_activity_text(msg: Any) -> str | None:
    """Extract activity text from a message"""
    try:
        if "Assistant" in msg.__class__.__name__:
            if hasattr(msg, "content") and msg.content:
                first_content = msg.content[0] if isinstance(msg.content, list) else msg.content
                if hasattr(first_content, "name"):
                    return f"🤖 Using: {first_content.name}()"
            return "🤖 Thinking..."
        elif "User" in msg.__class__.__name__:
            return "✓ Tool completed"
    except (AttributeError, IndexError):
        pass
    return None


def print_activity(msg: Any) -> None:
    """Print activity to console"""
    activity = get_activity_text(msg)
    if activity:
        print(activity)


async def send_query(
    prompt: str,
    continue_conversation: bool = False,
    permission_mode: Literal["default", "plan", "acceptEdits"] = "default",
    output_style: str | None = None,
    activity_handler: Callable[[Any], None | Any] = print_activity,
) -> tuple[str | None, list]:
    """
    Send a query to the Chief of Staff agent with all features integrated.

    Args:
        prompt: The query to send (can include slash commands like /budget-impact)
        activity_handler: Callback for activity updates (default: print_activity)
        continue_conversation: Continue the previous conversation if True
        permission_mode: "default" (execute), "plan" (think only), or "acceptEdits"
        output_style: Override output style (e.g., "executive", "technical", "board-report")

    Returns:
        Tuple of (result, messages) - result is the final text, messages is the full conversation

    Features automatically included/leveraged:
        - Memory: CLAUDE.md context loaded from chief_of_staff/CLAUDE.md
        - Subagents: financial-analyst and recruiter via Task tool (defined in .claude/agents)
        - Custom scripts: Python scripts in tools/ via Bash
        - Slash commands: Expanded from .claude/commands/
        - Output styles: Custom output styles defined in .claude/output-styles
        - Hooks: Triggered based on settings.json, defined in .claude/hooks
    """

    # Agent identity lives in build_agent_options() — the single source of truth
    # shared with the AgentCore entrypoint (Module 2+).
    options = build_agent_options(
        continue_conversation=continue_conversation,
        permission_mode=permission_mode,
        output_style=output_style,
    )

    result = None
    messages = []  # this is to append the messages ONLY for this agent turn

    try:
        async with ClaudeSDKClient(options=options) as agent:
            await agent.query(prompt=prompt)
            async for msg in agent.receive_response():
                messages.append(msg)
                if asyncio.iscoroutinefunction(activity_handler):
                    await activity_handler(msg)
                else:
                    activity_handler(msg)

                if hasattr(msg, "result"):
                    result = msg.result
    except Exception as e:
        print(f"❌ Query error: {e}")
        raise

    return result, messages
