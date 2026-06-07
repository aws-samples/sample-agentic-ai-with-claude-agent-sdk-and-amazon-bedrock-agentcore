#!/bin/bash
# Module 1 — local text-to-SQL agent. No AWS deploy here, just a local venv.
set -e
cd "$(dirname "$0")"
MODULE_NAME="agentic-analytics-module-1-local-agent"

# .env (region from current environment + model config)
cat > .env <<EOF
AWS_REGION=${AWS_REGION:-us-east-1}
CLAUDE_CODE_USE_BEDROCK=1
ANTHROPIC_MODEL=global.anthropic.claude-opus-4-6-v1
ANTHROPIC_SMALL_FAST_MODEL=global.anthropic.claude-haiku-4-5-20251001-v1:0
ATHENA_DATABASE=student_analytics
EOF

# Python dependencies
uv sync

# Register Jupyter kernel
.venv/bin/python -m ipykernel install \
  --user --name "$MODULE_NAME" --display-name "$MODULE_NAME"

echo ""
echo "✅ Setup complete — select the '$MODULE_NAME' kernel in the kernel picker (top-right)."
echo "   (Run Module 0 first if you haven't — this agent queries the Athena tables it creates.)"
