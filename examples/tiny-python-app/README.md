# Tiny Python App Example

This fake example demonstrates the workflow without private data.

Example task:

```text
Prompt 01: Add a /health endpoint, test it, update docs, and get reviewer signoff.
```

The example includes:

- `product-repo/`: a minimal Python app with tests.
- `control-workspace/`: example control files for a prompt.
- `expected-session-output/`: clearly fake receipt files.

No real agent logs are included.

## Run The Example Tests

```zsh
cd examples/tiny-python-app/product-repo
python3 -m unittest discover -s tests
```
