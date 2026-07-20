# Permission Model

The starter config uses OpenCode permissions to keep the workflow conservative.

## Defaults

- Read, grep, glob, and skills are allowed.
- Edits and shell commands are ask-by-default at the top level.
- External directories are denied.
- Sharing is disabled.
- Network lookup is ask-by-default.

## Builder

`minimax-builder` can edit generic product and session paths:

```text
product-repo/**
agent-sessions/**
```

It is denied reviewer-only files:

```text
*_PLAN_REVIEW.md
*_IMPLEMENTATION_REVIEW.md
*_SIGNOFF.md
```

It is also denied resolver-owned prompt locks ending in `*_MODELS.json`.

It can run common validation and inspection commands, but commit, push, rebase, hard reset, checkout revert, broad deletion, and privileged shell actions are denied.

## Reviewer

`glm-reviewer` can read and inspect the repo. It may write only review and signoff files under `agent-sessions/**`.

The reviewer must not edit product code. Review commands are limited to inspection and public-pack validation.

The internal `model-inference-smoke` agent has all tools denied and must return one exact inference sentinel. The separate `model-tool-smoke` agent denies all tools except reading `.opencode/model-smoke/FIXTURE.txt`; it must return one exact fixture-derived sentinel. These agents verify previously unseen or toolchain-stale exact cloud IDs before the resolver caches compact pass/fail metadata. Their raw output is not persisted.

## Practical Notes

Permissions are guardrails, not a complete sandbox. Use CI, code review, local sandboxing, and secret scanning for stronger enforcement.
