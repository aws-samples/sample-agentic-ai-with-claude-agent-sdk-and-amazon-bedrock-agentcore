# AgentCore Runtime container for the Chief of Staff agent.
#
# Why a container (not CodeZip)? The Claude Agent SDK ships a ~218MB native CLI
# binary (claude_agent_sdk/_bundled/claude). With CodeZip that binary lands
# WITHOUT the execute bit and the SDK fails at runtime ("Permission denied").
# Installing the SDK fresh inside a Linux/ARM64 image gives it the right arch
# and permissions.
#
# AgentCore Runtime requires linux/arm64. The base image must match.
FROM --platform=linux/arm64 public.ecr.aws/docker/library/python:3.11-slim-trixie

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    # Use Amazon Bedrock as the model provider (model id comes from ANTHROPIC_MODEL env).
    CLAUDE_CODE_USE_BEDROCK=1

# Node.js: the Claude Agent SDK's CLI resolution falls back to a Node-based
# `claude` if the bundled binary isn't usable. Having Node present makes the
# `npm install -g @anthropic-ai/claude-code` fallback below reliable.
RUN apt-get update \
    && apt-get install -y --no-install-recommends nodejs npm ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies (installs the SDK's Linux/arm64 bundled CLI with
# correct permissions, plus aws-opentelemetry-distro for the OTel wrapper).
COPY pyproject.toml ./
RUN pip install . \
    && pip cache purge || true

# Ensure a `claude` CLI is on PATH and executable (belt-and-suspenders for the
# SDK's _find_cli resolution: bundled binary first, then PATH).
RUN npm install -g @anthropic-ai/claude-code \
    && chmod -R a+rx "$(python -c 'import claude_agent_sdk, os; print(os.path.join(os.path.dirname(claude_agent_sdk.__file__), "_bundled"))')" || true

# Copy the agent bundle (code, CLAUDE.md, .claude/, scripts/, financial_data/).
COPY . /app

# AgentCore Runtime contract: HTTP on 0.0.0.0:8080 with /invocations + /ping.
# BedrockAgentCoreApp.run() implements that contract.
EXPOSE 8080

# NOTE: AgentCore wraps this with `opentelemetry-instrument` automatically when
# the agent's instrumentation.enableOtel is true (the default), so we do not add
# it here. We just run the entrypoint module.
CMD ["python", "agent_agentcore.py"]
