# Security Policy

## Public-Safe Defaults

This starter kit is designed to keep private agent material local by default. Session folders, screenshots, raw logs, `.env` files, and OpenCode session exports are ignored.

Before publishing anything, run:

```zsh
python3 scripts/validate_public_pack.py .
```

Then manually inspect public-bound files.

## Report A Vulnerability

If you find a security issue in this starter kit, open a GitHub security advisory or a private issue channel for the repository owner. Do not publish exploit details before maintainers have a chance to respond.

## Secrets And Private Data

Never commit:

- provider API keys or tokens;
- `.env` files;
- local auth files;
- private prompts or raw agent logs;
- screenshots containing private data;
- private repo URLs, task titles, customer data, or local machine paths.

## Tooling Boundaries

Treat MCP servers, browser automation, shell commands, package installers, and generated artifacts as security boundaries. Keep network and production credentials unavailable unless a human explicitly approves the risk.
