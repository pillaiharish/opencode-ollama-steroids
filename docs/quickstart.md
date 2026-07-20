# Quickstart

This guide sets up the control workspace, creates one prompt folder, and runs the builder/reviewer loop.

## 1. Check tools

```zsh
zsh scripts/doctor.zsh
```

You need OpenCode, Ollama, Python 3, and zsh.

## 2. Create local config

```zsh
cp project.local.env.example project.local.env
```

Edit `project.local.env` for your local product repo. Keep it uncommitted.

The default model families are `minimax-m` for the builder and `glm-` for the reviewer. The supported launch scripts select the highest stable numeric `:cloud` ID matching each family in the refreshed catalog exposed by the installed OpenCode CLI. This is a catalog-selection rule, not a universal newest-model claim.

## 3. Create a prompt

```zsh
zsh scripts/new_prompt.zsh project-slug prompt01 "Add a health endpoint, tests, docs, and reviewer signoff."
```

This creates:

```text
agent-sessions/project-slug/prompt01/
  PROMPT_CODER.md
  PROMPT_REVIEWER.md
  SESSION_README.md
```

## 4. Run agents

Builder:

```zsh
zsh scripts/run_builder.zsh project-slug prompt01
```

Reviewer:

```zsh
zsh scripts/run_reviewer.zsh project-slug prompt01
```

Both:

```zsh
zsh scripts/run_prompt_agents.zsh project-slug prompt01
```

The first run verifies unseen exact models with a no-tools inference sentinel and a controlled fixture-read sentinel, then writes `PROMPT01_MODELS.json` locally. Cloud smoke calls can consume quota. Later stages reuse that exact pair. To deliberately select later family releases for an existing prompt:

```zsh
zsh scripts/run_prompt_agents.zsh project-slug prompt01 --refresh-models
```

For a reusable localhost server:

```zsh
zsh scripts/start_headless_server.zsh
zsh scripts/run_builder.zsh project-slug prompt01 --attach http://localhost:4096
```

The server is model-agnostic. Each attached runner still passes its locked exact role model with `--model`.

## 5. Validate before publishing

```zsh
python3 scripts/validate_public_pack.py .
```

Keep raw logs, prompt folders, and screenshots local unless a human has manually redacted and approved them.
