#!/bin/bash
set -e
cd "$(dirname "$0")"

# .env (region from current environment + model config)
cat > .env <<EOF
AWS_REGION=${AWS_REGION:-ap-northeast-1}
CLAUDE_CODE_USE_BEDROCK=1
ANTHROPIC_MODEL=global.anthropic.claude-opus-4-6-v1
ANTHROPIC_SMALL_FAST_MODEL=global.anthropic.claude-haiku-4-5-20251001-v1:0
ATHENA_DATABASE=student_analytics
EOF

# Node.js 20 + AgentCore CLI (idempotent)
if ! command -v agentcore &>/dev/null; then
  if command -v apt-get &>/dev/null; then
    curl -fsSL https://deb.nodesource.com/setup_20.x | sudo bash -
    sudo apt-get install -y nodejs
  elif command -v yum &>/dev/null; then
    curl -fsSL https://rpm.nodesource.com/setup_20.x | sudo bash -
    sudo yum install -y nodejs-20.20.2
  else
    echo "❌ Unsupported package manager. Install Node.js 20 manually." && exit 1
  fi
  sudo npm install -g @aws/agentcore@0.17.0
fi
(cd agentcore/cdk && npm ci)

echo "✅ Setup complete."
