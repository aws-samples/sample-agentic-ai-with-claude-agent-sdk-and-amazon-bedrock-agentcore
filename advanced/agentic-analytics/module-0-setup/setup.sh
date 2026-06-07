#!/bin/bash
# Module 0 — install dependencies and register the Jupyter kernel.
# Infrastructure (S3 + Athena) is created from the notebook itself.
set -e
cd "$(dirname "$0")"
MODULE_NAME="agentic-analytics-module-0-setup"

# .env (region from current environment)
echo "AWS_REGION=${AWS_REGION:-us-east-1}" > .env

# Python dependencies
uv sync

# Register Jupyter kernel (so the notebook can run with these deps)
.venv/bin/python -m ipykernel install \
  --user --name "$MODULE_NAME" --display-name "$MODULE_NAME"

echo ""
echo "✅ Setup complete. Select the '$MODULE_NAME' kernel in the notebook, then run the cells."
