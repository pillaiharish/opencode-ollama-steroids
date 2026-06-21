# Session storage policy

Session artifacts are valuable for reproducibility and debugging. They are also sensitive.

## Store locally

Store under:

```text
agent-sessions/<project-slug>/<prompt-id>/
```

Typical files:

```text
PROMPT_CODER.md
PROMPT_REVIEWER.md
SESSION_README.md
PROMPTNN_PLAN.md
PROMPTNN_PLAN_REVIEW.md
PROMPTNN_IMPLEMENTATION.md
PROMPTNN_TEST_RESULTS.md
PROMPTNN_IMPLEMENTATION_REVIEW.md
PROMPTNN_FIXES.md
PROMPTNN_SIGNOFF.md
PROMPTNN_BUILDER.raw.log
PROMPTNN_REVIEWER.raw.log
redacted/
```

## Commit publicly

Commit only:

- reusable templates
- redacted summaries
- generic scripts
- public-safe examples

## Never commit publicly

- raw prompts from real work
- raw agent logs
- raw OpenCode exports
- `.env` files
- API keys
- local machine paths
- private screenshots
- customer data
- private roadmap details
- private issue/task titles

## Redaction steps

1. Run `python3 scripts/redact_sessions.py agent-sessions/<project-slug>/<prompt-id> --out tmp-redacted-session`.
2. Manually inspect every file in `tmp-redacted-session`.
3. Copy only summary material into public docs.
4. Never assume automated redaction caught everything.
