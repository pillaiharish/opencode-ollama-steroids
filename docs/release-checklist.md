# Release Checklist

Use this checklist before tagging or publishing a release.

- Run public-pack validation.
- Run zsh syntax checks.
- Run Python compile checks.
- Run tiny example tests.
- Scan for secrets and local paths.
- Confirm `agent-sessions/` and `screenshots/` only contain placeholders.
- Update release notes.
- Check `git status`.
- Tag the release.
- Publish the GitHub release.

Suggested commands:

```zsh
python3 scripts/validate_public_pack.py .
python3 -m py_compile scripts/*.py
zsh -n scripts/*.zsh
python3 -m unittest discover -s examples/tiny-python-app/product-repo/tests
find agent-sessions screenshots -type f -not -name ".gitkeep" -print
git status --short
```
