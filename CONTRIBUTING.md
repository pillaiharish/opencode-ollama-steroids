# Contributing

Thanks for improving this starter kit. Keep contributions public-safe and generic.

## Principles

- Use relative paths only.
- Do not include private prompts, real session logs, private screenshots, credentials, personal data, customer data, or local machine paths.
- Keep examples fake, minimal, and reproducible.
- Do not weaken validation or redaction checks to make a demo pass.
- Do not add model claims that are not backed by a clear source or test.

## Local Checks

Run these before opening a pull request:

```zsh
python3 scripts/validate_public_pack.py .
zsh -n scripts/*.zsh
python3 -m py_compile scripts/redact_sessions.py scripts/validate_public_pack.py
```

If you change the tiny Python example, also run its tests:

```zsh
cd examples/tiny-python-app/product-repo
python3 -m unittest discover -s tests
```

## Pull Request Notes

Summarize:

- what changed;
- what validation ran;
- whether any generated examples changed;
- whether the change affects public safety, redaction, permissions, or session storage.
