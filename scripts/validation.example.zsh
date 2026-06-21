#!/usr/bin/env zsh
set -euo pipefail

if [[ -f project.local.env ]]; then
  source project.local.env
fi

PRODUCT_DIR="${PRODUCT_DIR:-product-repo}"
PYTHON_BIN="${PYTHON_BIN:-.venv/bin/python}"
NPM_BIN="${NPM_BIN:-npm}"

cd "$PRODUCT_DIR"

if [[ -f pyproject.toml || -f setup.py ]]; then
  if [[ -x "$PYTHON_BIN" ]]; then
    "$PYTHON_BIN" -m pytest
  else
    python -m pytest
  fi
fi

if [[ -f package.json ]]; then
  "$NPM_BIN" test --if-present
  "$NPM_BIN" run build --if-present
  if grep -q '"@playwright/test"' package.json || [[ -d tests/playwright || -d e2e ]]; then
    npx playwright test
  fi
fi

# Add project-specific smoke, route, docs, or domain validation commands here.
