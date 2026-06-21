# MCP Playbook

OpenCode can use built-in tools and MCP servers. The goal is not to enable everything. The goal is to expose the smallest useful tool surface for the current job.

## Planning tools

Useful for:

- reading repository structure
- finding related implementation
- checking documentation
- reading issue/task context

Suggested posture:

- read/search allowed
- web/docs lookup on ask
- no write access

## Coding tools

Useful for:

- editing files
- running tests
- using language servers
- applying formatters
- inspecting package scripts

Suggested posture:

- edit allowed for builder only
- bash allowed for builder only inside the control/product workspace
- external directories denied
- package install commands on ask unless already approved

## Review tools

Useful for:

- `git diff`
- `git status`
- grep/search
- test report reading
- generated output inspection
- screenshots review

Suggested posture:

- reviewer can read and run safe inspection commands
- reviewer should not edit production code
- reviewer may write review/signoff files only under the current session folder

## Unit-test tools

Useful commands:

```zsh
python -m pytest
npm test
pnpm test
cargo test
go test ./...
```

Reviewer should block signoff if the builder claims success without command output or equivalent evidence.

## Browser-test tools

Useful for:

- route checks
- static-site smoke tests
- Playwright tests
- screenshot evidence
- accessibility smoke checks

Rules:

- localhost only by default
- no production credentials
- no private tabs in screenshots
- crop or redact screenshots before publishing

## Security-test tools

Useful categories:

- secret scanning
- dependency audit
- static analysis
- route exposure checks
- permission review
- generated artifact review

Example commands, depending on stack:

```zsh
gitleaks detect --no-git
trufflehog filesystem .
npm audit
pip-audit
semgrep scan
```

Do not blindly add tools that phone home or upload source code.

## MCP hygiene

- Use `opencode mcp add` to add servers deliberately.
- Keep MCP config reviewed.
- Prefer pinned versions.
- Remove unused servers.
- Keep network and OAuth-backed tools on ask.
- Never give MCP servers production credentials during routine coding.
- Treat MCP server definitions like code execution dependencies.
