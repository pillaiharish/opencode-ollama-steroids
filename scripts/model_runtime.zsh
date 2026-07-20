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

  if ! python3 scripts/model_resolver.py "${resolver_args[@]}" >/dev/null; then
    return 1
  fi
  if ! RESOLVED_BUILDER_MODEL="$(python3 scripts/model_resolver.py get \
    --session-dir "$session_dir" --prompt-id "$prompt_id" --role builder)"; then
    return 1
  fi
  if ! RESOLVED_REVIEWER_MODEL="$(python3 scripts/model_resolver.py get \
    --session-dir "$session_dir" --prompt-id "$prompt_id" --role reviewer)"; then
    return 1
  fi
  if ! OPENCODE_CONFIG_CONTENT="$(python3 scripts/model_resolver.py runtime-config \
    --builder-model "$RESOLVED_BUILDER_MODEL" \
    --reviewer-model "$RESOLVED_REVIEWER_MODEL")"; then
    return 1
  fi
  export RESOLVED_BUILDER_MODEL RESOLVED_REVIEWER_MODEL OPENCODE_CONFIG_CONTENT
}
