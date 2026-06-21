#!/usr/bin/env zsh
set -euo pipefail

PROJECT_SLUG_ARG="${1:-}"
PROMPT_ID="${2:-}"
TASK="${3:-Describe the feature, fix, or reviewable change here.}"

if [[ -z "$PROJECT_SLUG_ARG" || -z "$PROMPT_ID" ]]; then
  echo "Usage: scripts/new_prompt.zsh <project-slug> <prompt-id> [\"Task description\"]" >&2
  exit 2
fi

cd "$(dirname "$0")/.."

if [[ -f project.local.env ]]; then
  source project.local.env
fi

PROJECT_SLUG="$PROJECT_SLUG_ARG"
PRODUCT_DIR="${PRODUCT_DIR:-product-repo}"
SESSION_DIR="agent-sessions/${PROJECT_SLUG}/${PROMPT_ID}"
PROMPT_UPPER="${(U)PROMPT_ID}"

mkdir -p "$SESSION_DIR"

render_template() {
  local template="$1"
  local output="$2"
  sed \
    -e "s|__PROMPT_ID__|${PROMPT_ID}|g" \
    -e "s|__PROMPT_ID_UPPER__|${PROMPT_UPPER}|g" \
    -e "s|__PROJECT_SLUG__|${PROJECT_SLUG}|g" \
    -e "s|__PRODUCT_DIR__|${PRODUCT_DIR}|g" \
    "$template" | TASK_DETAIL="$TASK" perl -0pe 's/__TASK_DETAIL__/$ENV{TASK_DETAIL}/g' > "$output"
}

render_template templates/PROMPT_CODER_TEMPLATE.md "${SESSION_DIR}/PROMPT_CODER.md"
render_template templates/PROMPT_REVIEWER_TEMPLATE.md "${SESSION_DIR}/PROMPT_REVIEWER.md"
render_template templates/SESSION_README_TEMPLATE.md "${SESSION_DIR}/SESSION_README.md"

echo "Created ${SESSION_DIR}"
echo "Edit ${SESSION_DIR}/PROMPT_CODER.md before running agents."
