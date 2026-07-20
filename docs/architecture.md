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

Before either agent runs, the model resolver selects the highest stable numeric `:cloud` ID in the installed OpenCode CLI's refreshed Ollama catalog for each configured family. It verifies exact cloud-manifest readiness plus separate no-tools inference and controlled-file-read sentinels, then atomically writes a prompt-scoped model lock. That exact pair remains fixed for the prompt unless a human explicitly uses `--refresh-models`.

The prompt lock is authoritative and resolver-owned. A prompt-scoped filesystem guard serializes concurrent first runs. Replacement is transactional across both roles, and a failed refresh preserves the previous lock byte-for-byte. A compatible ignored last-known-good cache may be used only when catalog discovery fails; its entries are isolated by provider, both family selectors, and both exact-override values. A short-lived global cache guard serializes read/merge/replace operations across prompts while catalog access and verification remain outside that critical section. Runtime verification failures fail closed.

OpenCode and Ollama version changes re-verify the same locked pair. Catalog absence alone is not runtime disappearance. Each launcher obtains builder and reviewer from one immutable resolver result, uses the selected role ID explicitly with `--model`, and reinforces both mappings through runtime configuration. The reusable localhost server has no prompt model state. OpenCode's `small_model` remains independent.

The builder writes plans, implementation notes, test results, fix notes, and current state. The reviewer writes plan reviews, implementation reviews, and final signoff. Neither agent may edit the resolver-owned model lock.

Raw logs are useful locally, but they are ignored and not public material.

## Human Boundary

Agents do not commit, push, rebase, or force-push. After reviewer signoff, a human reviews the diff and decides whether to commit.
