# Release Checklist

Use this checklist before tagging or publishing a release.

- Run public-pack validation.
- Run zsh syntax checks.
- Run Python compile checks.
- Run model resolver unit and lifecycle tests.
- Run launcher integration tests, including attached-mode role-model authority.
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
python3 -m py_compile scripts/*.py tests/*.py
python3 -m unittest discover -s tests
zsh -n scripts/*.zsh
python3 -m unittest discover -s examples/tiny-python-app/product-repo/tests
find agent-sessions screenshots -type f -not -name ".gitkeep" -print
git status --short
```

The live compatibility check is opt-in because it refreshes the real catalog and can consume Ollama cloud quota. Run it intentionally when credentials and quota are available:

```zsh
RUN_LIVE_MODEL_TESTS=1 python3 -m unittest tests.test_model_resolver_live -v
```

The live test uses temporary ignored state, discovers the selected family heads dynamically, requires both exact smoke sentinels, and does not persist raw model output.
