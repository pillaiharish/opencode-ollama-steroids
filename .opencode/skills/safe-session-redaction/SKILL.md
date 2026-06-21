---
name: safe-session-redaction
description: Scan public-bound files and session material for secrets, local paths, emails, raw logs, screenshots, private prompts, .env data, and other leak patterns before publishing.
---

# Safe Session Redaction

Use this skill before publishing a repo, blog post, screenshot, example, release archive, or session summary.

## Scan Targets

Check public-bound files for:

- local absolute paths;
- emails, usernames, and personal data;
- API keys, tokens, passwords, private keys, and `.env` values;
- raw OpenCode session exports, JSONL event streams, and raw logs;
- private prompts or prompt history;
- screenshots and browser artifacts;
- private repo URLs, branch names, issue titles, customer names, or roadmap details.

## Required Commands

Run:

```zsh
python3 scripts/validate_public_pack.py .
```

For session material, run:

```zsh
python3 scripts/redact_sessions.py agent-sessions/<project-slug>/<prompt-id>
```

To produce redacted copies:

```zsh
python3 scripts/redact_sessions.py agent-sessions/<project-slug>/<prompt-id> --out tmp-redacted-session
```

## Manual Review

Automated redaction is not enough. Manually inspect:

- markdown files;
- script snippets;
- sample environment files;
- generated output;
- screenshots and browser captures;
- git remotes and URLs;
- logs copied into docs.

Do not publish if suspicious material remains.
