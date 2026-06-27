#!/bin/bash
set -e
cd "$(dirname "$0")"

# .env (region from current environment + model config)
cat > .env <<EOF
AWS_REGION=${AWS_REGION:-us-east-1}
CLAUDE_CODE_USE_BEDROCK=1
ANTHROPIC_MODEL=global.anthropic.claude-opus-4-6-v1
ANTHROPIC_SMALL_FAST_MODEL=global.anthropic.claude-haiku-4-5-20251001-v1:0
ATHENA_DATABASE=student_analytics
EOF

echo "✅ Setup complete."
