# OpenCode + Ollama Agent Rules

These rules define a public-safe control workspace for a two-agent OpenCode + Ollama workflow.

The workspace contains shared instructions, OpenCode config, local prompt/session folders, and a product repository. Do not add private prompts, raw logs, screenshots, usernames, emails, tokens, customer data, private repo details, or local absolute paths to public files.

## Workspace layout

Control workspace:

```text
.
```

Product repository, configured locally through `project.local.env`:

```text
${PRODUCT_DIR:-product-repo}
```

Agent session material:

```text
agent-sessions/<project-slug>/<prompt-id>/
```

Required path rule:

- Use relative paths only.
- Do not use absolute paths starting with `/Users`, `/home`, `/var/folders`, `C:\Users`, or other machine-specific prefixes.
- The product repo must be referenced through `PRODUCT_DIR` or a relative folder name such as `product-repo`.
- Do not copy private prompt text into public docs.

## Agents

### minimax-builder

Model: `ollama/minimax-m3:cloud`
Model family: `minimax-m`

Role: planner, coder, test runner, implementation reporter.

Responsibilities:

1. Read `AGENTS.md`.
2. Read the current prompt file under `agent-sessions/<project-slug>/<prompt-id>/PROMPT_CODER.md`.
3. Read previous redacted handoff files if present.
4. Create a scoped plan.
5. Request reviewer plan feedback before implementation when the workflow requires it.
6. Implement only the approved scope.
7. Run the required validation commands.
8. Write implementation notes, test results, fixes, and current state under the current session folder.
9. Fix blocking issues only inside the approved scope.
10. Stop after current prompt completion.

The builder may edit product code and run commands, but it must not:

- commit
- push
- rebase
- force-push
- start the next prompt
- weaken tests to pass
- delete unrelated files
- edit reviewer-only files
- publish raw prompts or raw sessions
- write files outside the product repo or current session folder unless explicitly instructed

Builder must never create, edit, or overwrite reviewer-only files ending in:

- `_PLAN_REVIEW.md`
- `_IMPLEMENTATION_REVIEW.md`
- `_SIGNOFF.md`

Builder and reviewer must never create, edit, or overwrite resolver-owned files ending in `_MODELS.json`.

### glm-reviewer

Model: `ollama/glm-5.2:cloud`
Model family: `glm-`

Role: strict reviewer.

Responsibilities:

1. Review the plan before implementation.
2. Review implementation diffs after changes.
3. Review tests, generated output, screenshots, browser-test results, and security posture.
4. Detect scope creep.
5. Detect weak tests.
6. Detect broken architecture boundaries.
7. Approve, request changes, or sign off.

The reviewer must not edit production code. The reviewer may write review and signoff files only under the current session folder.

Reviewer decision must be exactly one of:

- `APPROVED`
- `CHANGES_REQUESTED`
- `SIGNED_OFF`
- `NOT_SIGNED_OFF`

## Required workflow for every prompt

For each prompt:

1. Resolve, smoke-test when needed, and pin the exact builder/reviewer model pair.
2. Builder plan.
3. Reviewer plan review.
4. Builder implementation.
5. Builder test run.
6. Reviewer implementation review.
7. Builder fixes, if needed.
8. Builder reruns failing and full validation commands.
9. Reviewer final signoff.
10. Human reviews and decides whether to commit.

## Required session files

For `promptNN`, the prompt inputs are:

```text
agent-sessions/<project-slug>/promptNN/PROMPT_CODER.md
agent-sessions/<project-slug>/promptNN/PROMPT_REVIEWER.md
agent-sessions/<project-slug>/promptNN/SESSION_README.md
```

The resolver-owned model receipt is:

```text
agent-sessions/<project-slug>/promptNN/PROMPTNN_MODELS.json
```

Receipt files should use prompt-scoped names:

```text
agent-sessions/<project-slug>/promptNN/PROMPTNN_PLAN.md
agent-sessions/<project-slug>/promptNN/PROMPTNN_PLAN_REVIEW.md
agent-sessions/<project-slug>/promptNN/PROMPTNN_IMPLEMENTATION.md
agent-sessions/<project-slug>/promptNN/PROMPTNN_TEST_RESULTS.md
agent-sessions/<project-slug>/promptNN/PROMPTNN_IMPLEMENTATION_REVIEW.md
agent-sessions/<project-slug>/promptNN/PROMPTNN_FIXES.md
agent-sessions/<project-slug>/promptNN/PROMPTNN_SIGNOFF.md
agent-sessions/<project-slug>/promptNN/CURRENT_STATE.md
```

`PROMPTNN_MODELS.json` is resolver-owned, local, and ignored. On the prompt's first run, the supported launch scripts select the highest stable numeric `:cloud` ID in the installed OpenCode CLI's refreshed Ollama catalog for each configured family. They require exact cloud-manifest readiness plus no-tools inference and controlled-file-read smoke sentinels, then reuse that exact pair. Smoke calls may consume cloud quota. Change the pair only through `--refresh-models`; never hand-edit the lock or local cache.

Exact overrides must be full `ollama/<model>:cloud` IDs and fail closed if unavailable or unverifiable. Last-known-good fallback is restricted to catalog discovery failures with matching selectors and override context. Toolchain changes re-smoke the same locked pair instead of silently selecting a replacement.

Raw logs may be stored locally in the same folder, but they must remain gitignored.

## Required commands

Use the command file selected by the project:

```zsh
scripts/validation.example.zsh
```

When a project has custom gates, create a local copy that is **not** committed if it contains private paths:

```zsh
cp scripts/validation.example.zsh scripts/validation.local.zsh
```

Minimum expected validation categories:

- unit tests
- build or static generation
- smoke checks
- domain validation
- route checks, if static site or web app
- browser tests, if UI exists
- security/secret checks before publication

Never claim success unless required commands pass.

If a command fails:

1. Stop new feature work.
2. Fix the failure within scope.
3. Rerun the failed command.
4. Rerun the full required suite when practical.
5. Document failure and fix.

## Screenshot policy

Screenshots are useful for browser tests and UI review, but they are also a leak vector.

Allowed screenshots:

- localhost UI with no private data
- redacted visual diffs
- cropped failure screenshots that hide browser profile, usernames, shell prompts, tokens, URLs, customer names, and private issue titles

Not allowed in public docs:

- auth screens
- production dashboards
- terminal screenshots showing local paths or environment values
- browser tabs with private titles
- API responses containing personal or customer data

## MCP/tool policy

MCP servers and tools can make agents much more useful, but every external tool expands the blast radius.

Use MCP/tools by category:

- planning: repo search, docs lookup, issue tracker read-only
- coding: filesystem, shell, language server, package manager
- review: git diff, grep, static analysis, test report reader
- unit tests: test runner and coverage tools
- browser tests: Playwright or browser automation against localhost only
- security tests: dependency audit, secret scan, SAST, route exposure checks

Defaults:

- keep network tools on `ask`
- keep production credentials unavailable
- run browser tests on localhost only
- keep MCP server definitions reviewed and pinned
- remove unused MCP servers from config

## Publication policy

Before publishing any blog, post, repo, screenshot, or session summary:

```zsh
scripts/validate_public_pack.py .
```

Then manually inspect:

- all markdown files
- all screenshots
- all code snippets
- all shell commands
- all git remotes and URLs
- all sample `.env` files

The public story can describe the workflow and validation numbers. It must not publish the private prompts that produced the work.
