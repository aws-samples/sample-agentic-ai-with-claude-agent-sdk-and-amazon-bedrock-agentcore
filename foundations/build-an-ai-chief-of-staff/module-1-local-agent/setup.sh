#!/bin/bash
set -e
cd "$(dirname "$0")"
MODULE_NAME="$(basename "$PWD")"

# .env
[ -f .env ] || cp .env.example .env

# Python dependencies
uv sync

# Register Jupyter kernel
.venv/bin/python -m ipykernel install \
  --user --name "$MODULE_NAME" --display-name "$MODULE_NAME"

echo ""
echo "✅ Setup complete — now select the '$MODULE_NAME' kernel in the kernel picker (top-right)."
