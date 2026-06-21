# Builder Prompt

Prompt ID: `__PROMPT_ID__`
Project slug: `__PROJECT_SLUG__`
Product directory: `__PRODUCT_DIR__`

## Task

__TASK_DETAIL__

## Scope

Allowed:

- Work only inside the configured product directory and the current session folder.
- Create or update builder-owned receipt files for this prompt.
- Run validation commands and document results honestly.

Not allowed:

- Do not commit, push, rebase, force-push, or start another prompt.
- Do not edit reviewer-only files.
- Do not publish raw prompts, raw logs, screenshots, secrets, local absolute paths, or private project details.
- Do not weaken tests to pass.

## Required workflow

Follow `AGENTS.md`.

Write these files under the current session folder:

- `__PROMPT_ID_UPPER___PLAN.md`
- `__PROMPT_ID_UPPER___IMPLEMENTATION.md`
- `__PROMPT_ID_UPPER___TEST_RESULTS.md`
- `__PROMPT_ID_UPPER___FIXES.md`, only if needed
- `CURRENT_STATE.md`

Do not write reviewer files.

## Required commands

Run the project validation script:

```zsh
scripts/validation.example.zsh
```

If the product repo requires custom commands, use the project-specific validation script documented in `AGENTS.md` or `project.local.env`.

## Reporting requirements

Report:

- changed files
- tests run
- failures and fixes
- remaining risks
- whether generated files changed
- whether screenshots were used and where they are stored locally
