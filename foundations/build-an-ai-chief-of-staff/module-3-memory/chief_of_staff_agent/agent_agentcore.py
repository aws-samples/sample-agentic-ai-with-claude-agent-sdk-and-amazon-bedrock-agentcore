"""
Chief of Staff Agent — Amazon Bedrock AgentCore entrypoint (Module 3: Memory).

This is the THIN deployment wrapper. It holds the AgentCore plumbing only:
  - the BedrockAgentCoreApp + @app.entrypoint decorator,
  - parsing the request payload + identity,
  - retrieving memory before the turn and recording it after,
  - streaming the agent's response back to the caller.

It contains ZERO agent logic of its own — the agent's identity (system prompt,
tools, cwd, setting_sources) comes from `build_agent_options()` in agent.py, the
SAME function the local Module 1 `send_query()` uses. One source of truth.

What Module 3 adds vs. Module 2 (all plumbing, not agent logic):
  - a SECOND parameter `context` (see note below) to read the runtime session id,
  - a fixed `actor_id` (single-tenant workshop) so memory is scoped to one user,
  - `mem.retrieve_context()` before the turn → injected via `system_prompt_suffix`,
  - `mem.record_turn()` after the stream → persists the exchange for next time,
  - a `{"memory": false}` payload flag to toggle memory OFF for the A/B demo.

NOTE on the signature: AgentCore Runtime passes the request context ONLY when the
entrypoint declares a second parameter literally named `context`. Module 2's
`invoke(payload)` had one arg; Module 3 needs `invoke(payload, context)` to read
`context.session_id`. (Verified against bedrock_agentcore runtime/app.py.)

Run locally:   agentcore dev   (memory is unavailable locally → runs stateless)
Deployed:      AgentCore Runtime invokes `invoke` over HTTP; memory is live.
"""

import os

from dotenv import load_dotenv

from bedrock_agentcore import BedrockAgentCoreApp
from claude_agent_sdk import ClaudeSDKClient

# Reuse the agent's single source of truth.
from agent import build_agent_options

# Module 3's only net-new agent code: the memory layer.
from memory import get_memory

load_dotenv()

# On Amazon Bedrock the model comes from ANTHROPIC_MODEL; make sure the provider
# flag is set even if it wasn't injected as a runtime env var.
os.environ.setdefault("CLAUDE_CODE_USE_BEDROCK", "1")

# Single-tenant workshop: one fixed user identity. (Multi-tenant would derive
# this per-request from inbound identity; that's deliberately out of scope here.)
ACTOR_ID = "techstart-cos"

app = BedrockAgentCoreApp()


@app.entrypoint
async def invoke(payload, context):
    """AgentCore entrypoint. Expects {"prompt": "..."} and streams text chunks.

    Optional payload fields:
      - "memory": false  → skip memory retrieval AND recording for this turn
        (used by the demo's A/B: same prompt, same deployment, memory on vs off).
      - "actor_id": "..." → override the actor (handy for local dev / testing).

    Yields plain text as the agent produces it, so callers see a live stream.
    """
    prompt = (payload or {}).get("prompt") or (payload or {}).get("query")
    if not prompt:
        yield "Error: request payload must include a 'prompt' field, e.g. {\"prompt\": \"What's our runway?\"}"
        return

    memory_on = (payload or {}).get("memory", True)
    actor_id = (payload or {}).get("actor_id") or ACTOR_ID
    # Runtime-supplied conversation id (>=33 chars). None under local `agentcore dev`.
    session_id = getattr(context, "session_id", None)

    mem = get_memory(actor_id, session_id)

    # Turn START: recall what we know about this user, inject it into the prompt
    # via build_agent_options' suffix seam (keeps prompt assembly in agent.py).
    memory_block = mem.retrieve_context(prompt) if memory_on else ""
    options = build_agent_options(system_prompt_suffix=memory_block)

    chunks: list[str] = []
    async with ClaudeSDKClient(options=options) as agent:
        await agent.query(prompt)
        async for msg in agent.receive_response():
            for block in getattr(msg, "content", []) or []:
                text = getattr(block, "text", None)
                if text:
                    chunks.append(text)
                    yield text

    # Turn END: persist this exchange so future sessions can recall it.
    if memory_on:
        mem.record_turn(prompt, "".join(chunks))


if __name__ == "__main__":
    app.run()
