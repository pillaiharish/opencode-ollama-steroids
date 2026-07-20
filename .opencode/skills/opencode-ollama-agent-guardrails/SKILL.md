---
name: opencode-ollama-agent-guardrails
description: Enforce builder/reviewer discipline for OpenCode and Ollama workflows, including no commits, no raw prompt publishing, relative paths only, validation honesty, and human approval after signoff.
---

# OpenCode Ollama Agent Guardrails

Use this skill when configuring, running, reviewing, or publishing an OpenCode + Ollama multi-agent coding workflow.

## Required Agent Split

Builder agent:

- plans the current task;
- implements only approved scope;
- runs validation;
- writes implementation notes and test results;
- fixes blocking issues inside scope;
- stops for human review and commit approval.

Reviewer agent:

- reviews builder plans, diffs, tests, generated output, screenshots, and security posture;
- blocks scope creep and weak tests;
- writes only review and signoff files under the current session folder;
- never edits product code.

## Hard Rules

- Do not commit, push, rebase, force-push, or start another prompt.
- Do not publish raw prompts, raw OpenCode logs, session exports, or private screenshots.
- Do not use local absolute paths in public-bound files.
- Do not claim success unless the required validation commands passed.
- Do not weaken tests to pass.
- Do not let reviewers edit production code.
- Do not let agents edit resolver-owned prompt model locks ending in `_MODELS.json`.
- Stop after final signoff so a human can inspect and decide whether to commit.

## Session Rules

Use:

```text
agent-sessions/<project-slug>/<prompt-id>/
```

Product edits belong only under the configured product repo, usually:

```text
product-repo/
```

Raw logs may stay local in the session folder, but they must remain ignored.

## Decision Vocabulary

Reviewer decisions must be exactly one of:

- `APPROVED`
- `CHANGES_REQUESTED`
- `SIGNED_OFF`
- `NOT_SIGNED_OFF`
