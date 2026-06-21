#!/usr/bin/env zsh
set -euo pipefail

PROJECT_SLUG="${1:-}"
PROMPT_ID="${2:-}"
ATTACH_URL=""

if [[ -z "$PROJECT_SLUG" || -z "$PROMPT_ID" ]]; then
  echo "Usage: scripts/run_prompt_agents.zsh <project-slug> <prompt-id> [--attach http://localhost:4096]" >&2
  exit 2
fi

shift 2
while [[ $# -gt 0 ]]; do
  case "$1" in
    --attach)
      ATTACH_URL="${2:-}"
      if [[ -z "$ATTACH_URL" ]]; then
        echo "--attach requires a URL" >&2
        exit 2
      fi
      shift 2
      ;;
    *)
      echo "Unknown argument: $1" >&2
      exit 2
      ;;
  esac
done

cd "$(dirname "$0")/.."

ATTACH_ARGS=()
if [[ -n "$ATTACH_URL" ]]; then
  ATTACH_ARGS=(--attach "$ATTACH_URL")
fi

print "==> Running minimax-builder for ${PROJECT_SLUG}/${PROMPT_ID}"
zsh scripts/run_builder.zsh "$PROJECT_SLUG" "$PROMPT_ID" "${ATTACH_ARGS[@]}"

print "==> Running glm-reviewer for ${PROJECT_SLUG}/${PROMPT_ID}"
zsh scripts/run_reviewer.zsh "$PROJECT_SLUG" "$PROMPT_ID" "${ATTACH_ARGS[@]}"

print "==> Done. Inspect agent-sessions/${PROJECT_SLUG}/${PROMPT_ID}. Raw logs are gitignored."
