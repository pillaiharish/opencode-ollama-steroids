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

It can run common validation and inspection commands, but commit, push, rebase, hard reset, checkout revert, broad deletion, and privileged shell actions are denied.

## Reviewer

`glm-reviewer` can read and inspect the repo. It may write only review and signoff files under `agent-sessions/**`.

The reviewer must not edit product code. Review commands are limited to inspection and public-pack validation.

## Practical Notes

Permissions are guardrails, not a complete sandbox. Use CI, code review, local sandboxing, and secret scanning for stronger enforcement.
