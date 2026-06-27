#!/bin/bash
set -e
cd "$(dirname "$0")"

# .env (region from current environment)
echo "AWS_REGION=${AWS_REGION:-us-east-1}" > .env

echo "✅ Setup complete."
