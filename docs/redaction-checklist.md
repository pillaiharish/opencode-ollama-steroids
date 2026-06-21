# Redaction Checklist

Use this before publishing docs, examples, posts, screenshots, session summaries, or release archives.

## Text

Check for:

- real names not intended for publication;
- usernames and handles;
- email addresses;
- phone numbers;
- local machine paths;
- private repo URLs;
- branch names that reveal roadmap;
- customer names;
- private issue titles;
- credentials, tokens, passwords, and private keys;
- raw prompts;
- raw session outputs.

## Code Snippets

Check for:

- real paths;
- real hostnames;
- credential-like placeholders that look usable;
- production URLs;
- internal package names;
- private registry URLs;
- comments containing sensitive detail.

## Screenshots

Check for:

- browser profile names or avatars;
- private browser tabs;
- sensitive URL bar content;
- production hostnames;
- auth cookies or tokens;
- terminal prompt usernames or hostnames;
- local filesystem paths;
- private issue names;
- customer or personal data.

## Commands

Run:

```zsh
python3 scripts/validate_public_pack.py .
python3 scripts/redact_sessions.py agent-sessions/project-slug/prompt01
```

Then manually inspect every public-bound file.
