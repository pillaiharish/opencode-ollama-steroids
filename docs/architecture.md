# Architecture

The repo is a control workspace. It holds process rules, OpenCode config, prompt templates, skills, validation scripts, and local session receipts.

## Control Workspace

Important files:

- `AGENTS.md`: shared policy for agents.
- `opencode.json`: OpenCode model, agent, and permission config.
- `.opencode/agents/`: agent prompt files referenced by OpenCode.
- `.opencode/skills/`: reusable guardrails for agent runs.
- `templates/`: prompt folder templates.
- `scripts/`: local automation.
- `docs/`: public-safe documentation.
- `examples/`: fake and minimal examples.

## Product Repo

Product edits belong under `product-repo/` or another relative directory configured in `project.local.env`.

The control workspace can sit beside or above the product repo. Agents should not write outside the product repo and current session folder.

## Session Receipts

Each task gets a folder:

```text
agent-sessions/<project-slug>/<prompt-id>/
```

The builder writes plans, implementation notes, test results, fix notes, and current state. The reviewer writes plan reviews, implementation reviews, and final signoff.

Raw logs are useful locally, but they are ignored and not public material.

## Human Boundary

Agents do not commit, push, rebase, or force-push. After reviewer signoff, a human reviews the diff and decides whether to commit.
