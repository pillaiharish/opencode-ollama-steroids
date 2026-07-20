#!/usr/bin/env zsh
set -euo pipefail

missing=0

check_command() {
  local name="$1"
  local hint="$2"

  if command -v "$name" >/dev/null 2>&1; then
    echo "ok: ${name} found"
  else
    echo "missing: ${name}" >&2
    echo "  ${hint}" >&2
    missing=1
  fi
}

check_command opencode "Install OpenCode, then run this script again."
check_command ollama "Install Ollama and confirm the provider works with OpenCode."
check_command python3 "Install Python 3 for validation and redaction scripts."
check_command zsh "Install zsh or run on a system where zsh is available."

if [[ ! -f project.local.env ]]; then
  echo "note: project.local.env is not present"
  echo "      copy project.local.env.example to project.local.env for local runs"
fi

if [[ "$missing" -ne 0 ]]; then
  exit 1
fi

echo "ok: OpenCode version $(opencode --version 2>&1 | head -n 1)"
echo "ok: $(ollama --version 2>&1 | head -n 1)"
echo "ok: $(python3 --version 2>&1 | head -n 1)"
echo "ok: $(zsh --version 2>&1 | head -n 1)"

if ! opencode models --help 2>&1 | grep -q -- "--refresh"; then
  echo "missing: this OpenCode version does not support model catalog refresh" >&2
  echo "  Upgrade OpenCode manually, then run this script again." >&2
  exit 1
fi

echo "ok: OpenCode model catalog refresh supported"

if ! python3 scripts/model_resolver.py self-check >/dev/null; then
  echo "missing: strict model catalog parser self-check failed" >&2
  exit 1
fi

echo "ok: strict model catalog parser self-check passed"

echo "doctor passed"
