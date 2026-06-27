#!/bin/bash
set -e
cd "$(dirname "$0")"

# .env
[ -f .env ] || cp .env.example .env

echo "✅ Setup complete."
