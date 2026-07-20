#!/usr/bin/env zsh

# Shared model-family resolution for the supported OpenCode launch scripts.

load_model_config() {
  local environment_builder_model="${BUILDER_MODEL:-}"
  local environment_reviewer_model="${REVIEWER_MODEL:-}"
  local environment_builder_family="${BUILDER_MODEL_FAMILY:-}"
  local environment_reviewer_family="${REVIEWER_MODEL_FAMILY:-}"

  if [[ -f project.local.env ]]; then
    set -a
    source project.local.env
    set +a
  fi

  if [[ -n "$environment_builder_model" ]]; then
    BUILDER_MODEL="$environment_builder_model"
  fi
  if [[ -n "$environment_reviewer_model" ]]; then
    REVIEWER_MODEL="$environment_reviewer_model"
  fi
  if [[ -n "$environment_builder_family" ]]; then
    BUILDER_MODEL_FAMILY="$environment_builder_family"
  fi
  if [[ -n "$environment_reviewer_family" ]]; then
    REVIEWER_MODEL_FAMILY="$environment_reviewer_family"
  fi

  BUILDER_MODEL_FAMILY="${BUILDER_MODEL_FAMILY:-minimax-m}"
  REVIEWER_MODEL_FAMILY="${REVIEWER_MODEL_FAMILY:-glm-}"
}

resolve_prompt_models() {
  local session_dir="$1"
  local prompt_id="$2"
  local refresh_models="${3:-0}"
  local project_slug="${4:-${session_dir:h:t}}"
  local resolved_json resolved_lines
  local -a resolved_models
  local resolver_args=(
    resolve
    --session-dir "$session_dir"
    --prompt-id "$prompt_id"
    --project-slug "$project_slug"
    --builder-family "$BUILDER_MODEL_FAMILY"
    --reviewer-family "$REVIEWER_MODEL_FAMILY"
  )

  if [[ -n "${BUILDER_MODEL:-}" ]]; then
    resolver_args+=(--builder-model "$BUILDER_MODEL")
  fi
  if [[ -n "${REVIEWER_MODEL:-}" ]]; then
    resolver_args+=(--reviewer-model "$REVIEWER_MODEL")
  fi
  if [[ "$refresh_models" == "1" ]]; then
    resolver_args+=(--refresh-models)
  fi

  if ! resolved_json="$(python3 scripts/model_resolver.py "${resolver_args[@]}")"; then
    return 1
  fi
  if ! resolved_lines="$(print -r -- "$resolved_json" | python3 -c '
import json
import re
import sys

try:
    value = json.load(sys.stdin)
except (json.JSONDecodeError, OSError) as exc:
    raise SystemExit(f"invalid resolver JSON: {exc}")

pattern = re.compile(r"^ollama/[a-z0-9][a-z0-9._/-]*:cloud$")
if not isinstance(value, dict):
    raise SystemExit("invalid resolver result: expected an object")

builder = value.get("builder")
reviewer = value.get("reviewer")
if not isinstance(builder, str) or not pattern.fullmatch(builder):
    raise SystemExit("invalid resolver result: missing strict builder cloud ID")
if not isinstance(reviewer, str) or not pattern.fullmatch(reviewer):
    raise SystemExit("invalid resolver result: missing strict reviewer cloud ID")

print(builder)
print(reviewer)
')"; then
    echo "Could not parse the atomic model resolver result." >&2
    return 1
  fi
  resolved_models=("${(@f)resolved_lines}")
  if (( ${#resolved_models[@]} != 2 )); then
    echo "Invalid model resolver result: expected exactly two model IDs." >&2
    return 1
  fi
  RESOLVED_BUILDER_MODEL="${resolved_models[1]}"
  RESOLVED_REVIEWER_MODEL="${resolved_models[2]}"
  if ! OPENCODE_CONFIG_CONTENT="$(python3 scripts/model_resolver.py runtime-config \
    --builder-model "$RESOLVED_BUILDER_MODEL" \
    --reviewer-model "$RESOLVED_REVIEWER_MODEL")"; then
    return 1
  fi
  export RESOLVED_BUILDER_MODEL RESOLVED_REVIEWER_MODEL OPENCODE_CONFIG_CONTENT
}
