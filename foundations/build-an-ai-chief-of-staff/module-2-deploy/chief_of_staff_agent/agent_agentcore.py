"""
Chief of Staff Agent — Amazon Bedrock AgentCore entrypoint.

This is the THIN deployment wrapper. It holds the AgentCore plumbing only:
  - the BedrockAgentCoreApp + @app.entrypoint decorator,
  - parsing the request payload,
  - streaming the agent's response back to the caller.

It contains ZERO agent logic of its own — the agent's identity (system prompt,
tools, cwd, setting_sources) comes from `build_agent_options()` in agent.py, the
SAME function the local Module 1 `send_query()` uses. One source of truth.

Run locally:   agentcore dev
Deployed:      AgentCore Runtime invokes the `invoke` entrypoint over HTTP.
"""

import os

from dotenv import load_dotenv

from bedrock_agentcore import BedrockAgentCoreApp
from claude_agent_sdk import ClaudeSDKClient

# Reuse the agent's single source of truth.
from agent import build_agent_options

load_dotenv()

# On Amazon Bedrock the model comes from ANTHROPIC_MODEL; make sure the provider
# flag is set even if it wasn't injected as a runtime env var.
os.environ.setdefault("CLAUDE_CODE_USE_BEDROCK", "1")

app = BedrockAgentCoreApp()


@app.entrypoint
async def invoke(payload: dict):
    """AgentCore entrypoint. Expects {"prompt": "..."} and streams text chunks.

    Yields plain text as the agent produces it, so callers see a live stream
    rather than waiting for the whole turn to finish.
    """
    prompt = (payload or {}).get("prompt") or (payload or {}).get("query")
    if not prompt:
        yield "Error: request payload must include a 'prompt' field, e.g. {\"prompt\": \"What's our runway?\"}"
        return

    # Identical configuration to the local agent (Module 1).
    options = build_agent_options()

    async with ClaudeSDKClient(options=options) as agent:
        await agent.query(prompt)
        async for msg in agent.receive_response():
            for block in getattr(msg, "content", []) or []:
                text = getattr(block, "text", None)
                if text:
                    yield text


if __name__ == "__main__":
    app.run()
