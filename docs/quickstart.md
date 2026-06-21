# Quickstart

This guide sets up the control workspace, creates one prompt folder, and runs the builder/reviewer loop.

## 1. Check tools

```zsh
scripts/doctor.zsh
```

You need OpenCode, Ollama, Python 3, and zsh.

## 2. Create local config

```zsh
cp project.local.env.example project.local.env
```

Edit `project.local.env` for your local product repo. Keep it uncommitted.

## 3. Create a prompt

```zsh
scripts/new_prompt.zsh project-slug prompt01 "Add a health endpoint, tests, docs, and reviewer signoff."
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
scripts/run_builder.zsh project-slug prompt01
```

Reviewer:

```zsh
scripts/run_reviewer.zsh project-slug prompt01
```

Both:

```zsh
scripts/run_prompt_agents.zsh project-slug prompt01
```

## 5. Validate before publishing

```zsh
python3 scripts/validate_public_pack.py .
```

Keep raw logs, prompt folders, and screenshots local unless a human has manually redacted and approved them.
