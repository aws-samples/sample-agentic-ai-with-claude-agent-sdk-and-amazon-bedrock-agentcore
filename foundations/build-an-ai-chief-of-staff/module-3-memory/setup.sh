#!/bin/bash
set -e
cd "$(dirname "$0")"

# .env
[ -f .env ] || cp .env.example .env

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
