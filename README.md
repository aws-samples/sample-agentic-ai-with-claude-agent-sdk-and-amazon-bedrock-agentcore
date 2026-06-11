# Agentic AI with Claude Agent SDK + Amazon Bedrock AgentCore

A hands-on workshop that progressively builds, deploys, and operationalizes AI agents using the [Claude Agent SDK](https://docs.anthropic.com/en/docs/agents-and-tools/claude-agent-sdk) and [Amazon Bedrock AgentCore](https://aws.amazon.com/bedrock/agentcore/).

## Workshop structure

The workshop is organized as a progressive ladder across two tracks. Each module builds on the previous one, adding a new capability while keeping the agent code as the single source of truth.

### Foundations — Build an AI Chief of Staff

A lightweight agent (fictional startup "TechStart Inc" — runway, burn, hiring analysis) that requires only AWS credentials + Bedrock model access.

| Module | What you learn |
|--------|---------------|
| [1 — Local Agent](foundations/build-an-ai-chief-of-staff/module-1-local-agent/) | Build an agent with `ClaudeSDKClient`, system prompts, `CLAUDE.md`, skills, and multi-turn conversation |
| [2 — Deploy](foundations/build-an-ai-chief-of-staff/module-2-deploy/) | Package and deploy the agent to AgentCore Runtime (Container/ECR), invoke over HTTP |
| [3 — Memory](foundations/build-an-ai-chief-of-staff/module-3-memory/) | Add cross-session memory with AgentCore Memory (short-term events + long-term extraction) |
| [4 — Observability](foundations/build-an-ai-chief-of-staff/module-4-observability/) | Trace agent execution in CloudWatch GenAI dashboards via OpenTelemetry |

### Advanced — Agentic Analytics (optional)

A text-to-SQL agent that queries a Student Analytics dataset on Athena. Requires the Athena/S3 infrastructure set up in Module 0.

| Module | What you learn |
|--------|---------------|
| [0 — Setup](advanced/agentic-analytics/module-0-setup/) | Provision S3, Glue catalog, and Athena tables for the demo dataset |
| [1 — Local Agent](advanced/agentic-analytics/module-1-local-agent/) | Build a BI agent that translates natural language to SQL |
| [2 — Deploy + Observe](advanced/agentic-analytics/module-2-deploy/) | Full CLI lifecycle: create, deploy, invoke, and trace the agent |
| [3 — Follow-up](advanced/agentic-analytics/module-3-follow-up/) | Handle ambiguous queries with clarification questions and session resume |

## Prerequisites

- AWS account with Amazon Bedrock model access (Claude Sonnet)
- AWS CLI configured with appropriate credentials
- Python 3.11
- [uv](https://docs.astral.sh/uv/) (Python package manager)
- Node.js 18+ (for the `@aws/agentcore` CLI)

## Getting started

Each module is self-contained with its own virtual environment. To start a module:

```bash
cd foundations/build-an-ai-chief-of-staff/module-1-local-agent
./setup.sh          # installs deps, registers Jupyter kernel
```

Then open the module's notebook (e.g. `module-1-local-agent.ipynb`) and follow along.

## Key design decisions

- **Bedrock, not the Anthropic API** — model selection comes from environment variables (`ANTHROPIC_MODEL` + `CLAUDE_CODE_USE_BEDROCK=1`), not hardcoded in agent code.
- **Container builds** — the Claude Agent SDK bundles a native CLI that requires correct permissions and architecture; Container builds (`pip install` on Linux/arm64) handle this correctly where CodeZip cannot.
- **Single source of truth** — each track has one `build_agent_options()` function shared across all modules; drift-guard tests enforce byte-identical copies.
- **`@aws/agentcore` CLI** — all deployment uses the current npm CLI (`agentcore create/deploy/invoke/remove`), not the deprecated starter toolkit.
