# AgentCore Runtime container for the Agentic Analytics agent.
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
    CLAUDE_CODE_USE_BEDROCK=1 \
    CLAUDE_CODE_ENABLE_TELEMETRY=1 \
    CLAUDE_CODE_ENHANCED_TELEMETRY_BETA=1 \
    # Observability: activate the ADOT pipeline so the runtime exports OTEL traces/spans
    # to CloudWatch. For a BYO container with our own CMD, we own the launch command, so
    # WE wrap it with `opentelemetry-instrument` (the runtime only auto-injects that for
    # CLI-managed builds). These env vars configure the AWS Distro for OpenTelemetry.
    AGENT_OBSERVABILITY_ENABLED=true \
    OTEL_PYTHON_DISTRO=aws_distro \
    OTEL_PYTHON_CONFIGURATOR=aws_configurator \
    OTEL_EXPORTER_OTLP_PROTOCOL=http/protobuf \
    OTEL_TRACES_EXPORTER=otlp \
    OTEL_METRICS_EXPORTER=otlp \
    OTEL_LOGS_EXPORTER=otlp \
    # Disable the openinference claude_agent_sdk auto-instrumentor — it emits a competing
    # span tree that breaks the evaluator's span↔log matching.
    OTEL_PYTHON_DISABLED_INSTRUMENTATIONS=claude_agent_sdk

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

# Copy the agent bundle (code, CLAUDE.md, .claude/, tools/, data/metadata/).
COPY . /app

# AgentCore Runtime contract: HTTP on 0.0.0.0:8080 with /invocations + /ping.
EXPOSE 8080

# Wrap the entrypoint with `opentelemetry-instrument` (from aws-opentelemetry-distro)
# so ADOT auto-instruments the agent and exports traces to CloudWatch GenAI Observability.
CMD ["opentelemetry-instrument", "python", "agent_agentcore.py"]
