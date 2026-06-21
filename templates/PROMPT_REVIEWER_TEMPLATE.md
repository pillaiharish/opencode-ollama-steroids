# Reviewer Prompt

Prompt ID: `__PROMPT_ID__`
Project slug: `__PROJECT_SLUG__`
Product directory: `__PRODUCT_DIR__`

## Review target

Review the builder's plan, diff, validation results, generated output, browser evidence, screenshots, and security posture for the current prompt.

## Required workflow

Follow `AGENTS.md`.

Write review files under the current session folder only:

- `__PROMPT_ID_UPPER___PLAN_REVIEW.md`
- `__PROMPT_ID_UPPER___IMPLEMENTATION_REVIEW.md`
- `__PROMPT_ID_UPPER___SIGNOFF.md`

Do not edit product code.

## Required review checks

- Is scope correct?
- Were architecture boundaries preserved?
- Are tests meaningful rather than superficial?
- Did required validation commands pass?
- Were generated files changed deliberately?
- Are screenshots sanitized?
- Are secrets, local absolute paths, private prompts, emails, usernames, or customer data absent from public-bound files?

## Decision vocabulary

Use exactly one decision:

- `APPROVED`
- `CHANGES_REQUESTED`
- `SIGNED_OFF`
- `NOT_SIGNED_OFF`
