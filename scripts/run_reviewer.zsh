#!/usr/bin/env zsh
set -euo pipefail

PROJECT_SLUG="${1:-}"
PROMPT_ID="${2:-}"
ATTACH_URL=""
REVIEWER_MODEL="${REVIEWER_MODEL:-ollama/glm-5.1:cloud}"

if [[ -z "$PROJECT_SLUG" || -z "$PROMPT_ID" ]]; then
  echo "Usage: scripts/run_reviewer.zsh <project-slug> <prompt-id> [--attach http://localhost:4096]" >&2
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

SESSION_DIR="agent-sessions/${PROJECT_SLUG}/${PROMPT_ID}"
PROMPT_FILE="${SESSION_DIR}/PROMPT_REVIEWER.md"
PROMPT_UPPER="${(U)PROMPT_ID}"

if [[ ! -f AGENTS.md || ! -f opencode.json ]]; then
  echo "Run from the control workspace containing AGENTS.md and opencode.json." >&2
  exit 1
fi

if [[ ! -f "$PROMPT_FILE" ]]; then
  echo "Prompt file not found: ${PROMPT_FILE}" >&2
  echo "Create it with: scripts/new_prompt.zsh ${PROJECT_SLUG} ${PROMPT_ID} \"Task\"" >&2
  exit 1
fi

OPENCODE_ATTACH_ARGS=()
if [[ -n "$ATTACH_URL" ]]; then
  OPENCODE_ATTACH_ARGS=(--attach "$ATTACH_URL")
fi

mkdir -p "$SESSION_DIR"

opencode run \
  --model "$REVIEWER_MODEL" \
  --agent glm-reviewer \
  --dir . \
  "${OPENCODE_ATTACH_ARGS[@]}" \
  "$(cat "$PROMPT_FILE")" \
  | tee "${SESSION_DIR}/${PROMPT_UPPER}_REVIEWER.raw.log"
