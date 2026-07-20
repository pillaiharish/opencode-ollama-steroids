# opencode-ollama-steroids

Stop vibe-coding blind.

A receipt-first OpenCode + Ollama multi-agent workflow for headless agent runs with builder/reviewer agents, local session receipts, skills, validation gates, screenshots policy, and redaction tooling.

This repo is a public-safe starter kit. Clone it beside or above a product repository, create prompt folders under `agent-sessions/`, run a builder agent, run a reviewer agent, keep receipts locally, and publish only sanitized templates or summaries.

It intentionally does not include private prompts, raw session logs, real screenshots, local machine paths, credentials, customer data, or generated private project artifacts.

## What this gives you

- `opencode.json` configured for two Ollama-backed workflow agents and two narrowly scoped compatibility probes.
- `minimax-builder` for planning, implementation, validation, and implementation notes.
- `glm-reviewer` for strict plan, diff, test, screenshot, and security review.
- Update-resilient, per-prompt resolution of stable MiniMax and GLM Ollama cloud releases, with two-stage smoke tests and exact model locks.
- Local session folders that keep prompts and receipts out of public docs.
- Reusable `.opencode/skills/` guardrails for agent discipline, redaction, and test evidence.
- Scripts for creating prompt folders, running agents headlessly, redacting sessions, validating the public pack, and checking local prerequisites.
- Docs, templates, and a tiny Python example that show the workflow without private data.

## Why this exists

AI coding gets risky when the process is invisible. A useful agent workflow needs a plan, review, tests, failure notes, redaction, and a human commit boundary.

This starter kit is built around one simple loop:

```text
Prompt -> builder plan -> reviewer plan review -> builder implementation -> validation -> reviewer signoff -> human commit
```

The models matter, but the receipts matter more. The point is to make agent mistakes visible before code is merged.

## Quickstart

Install OpenCode and Ollama, then check your local tools:

```zsh
zsh scripts/doctor.zsh
```

Create a local project config:

```zsh
cp project.local.env.example project.local.env
```

Edit `project.local.env` for your own machine. Keep it uncommitted.

Create a prompt folder:

```zsh
zsh scripts/new_prompt.zsh tiny-python-app prompt01 "Add a health endpoint"
```

Run the builder:

```zsh
zsh scripts/run_builder.zsh tiny-python-app prompt01
```

Run the reviewer:

```zsh
zsh scripts/run_reviewer.zsh tiny-python-app prompt01
```

Or run both in sequence:

```zsh
zsh scripts/run_prompt_agents.zsh tiny-python-app prompt01
```

For repeated runs, start the model-agnostic local headless server:

```zsh
zsh scripts/start_headless_server.zsh
zsh scripts/run_builder.zsh tiny-python-app prompt01 --attach http://localhost:4096
```

The attached runner still supplies the prompt's exact role model through `--model`; the server is not restarted or pinned per prompt.

The examples use `zsh scripts/...` so they do not depend on executable permissions. You may optionally run:

```zsh
chmod +x scripts/*.zsh
```

## Expected Structure

```text
.
  AGENTS.md
  opencode.json
  project.local.env.example
  .opencode/
    agents/
    skills/
  agent-sessions/
    project-slug/
      prompt01/
        PROMPT_CODER.md
        PROMPT_REVIEWER.md
        SESSION_README.md
        PROMPT01_MODELS.json
        receipts and raw logs, gitignored
  product-repo/
  scripts/
  templates/
  docs/
  examples/
```

Use relative paths only. Keep product edits under `product-repo/` or the product directory configured locally. Keep session receipts under `agent-sessions/<project-slug>/<prompt-id>/`.

## Creating Prompts

```zsh
zsh scripts/new_prompt.zsh <project-slug> <prompt-id> ["Task description"]
```

The script creates:

```text
agent-sessions/<project-slug>/<prompt-id>/
  PROMPT_CODER.md
  PROMPT_REVIEWER.md
  SESSION_README.md
```

The generated files are local working material and are ignored by default. Publish only redacted summaries.

## Running Agents

Builder:

```zsh
zsh scripts/run_builder.zsh <project-slug> <prompt-id>
```

Reviewer:

```zsh
zsh scripts/run_reviewer.zsh <project-slug> <prompt-id>
```

Both:

```zsh
zsh scripts/run_prompt_agents.zsh <project-slug> <prompt-id>
```

With a local server:

```zsh
zsh scripts/start_headless_server.zsh
zsh scripts/run_prompt_agents.zsh <project-slug> <prompt-id> --attach http://localhost:4096
```

The scripts write raw logs under the session folder. Raw logs are ignored and must not be published.

On the first supported launch for a prompt, the resolver refreshes the installed OpenCode CLI's Ollama catalog and selects the highest stable numeric `:cloud` identifier matching each configured family prefix. "Highest" is a numeric component comparison, so `5.10` is later than `5.2`; previews, malformed tags, other providers, and local variants are excluded. This is a precise catalog rule, not a claim that the result is Ollama's universally newest or best model.

Each previously unseen exact ID must pass cloud-manifest readiness, an exact no-tools inference sentinel, and an exact controlled-file-read tool sentinel. These probes can consume cloud quota. Only compact status metadata is retained; raw model responses are not written to locks or caches. The resolver then atomically writes the ignored `PROMPTNN_MODELS.json` receipt, and every later builder, reviewer, fix, signoff, and attached run reuses that exact pair.

To deliberately replace a prompt lock after both new models pass verification:

```zsh
zsh scripts/run_prompt_agents.zsh tiny-python-app prompt01 --refresh-models
```

Last-known-good fallback is deliberately narrow: it is considered only when catalog discovery or refresh fails, and only for the same family selectors and exact-override context. Model readiness failures, inference failures, tool failures, and invalid exact overrides fail closed instead of hiding a broken candidate. A failed explicit refresh preserves the previous lock byte-for-byte. The resolver never crosses model families or downloads local heavyweight variants.

A locked ID missing from a later catalog is not treated as proof that the runtime model disappeared. Normal reuse checks the exact locked cloud manifest and keeps the lock if it is runnable. If the OpenCode version, Ollama version, or resolver verification version changes, the same locked pair is re-smoked; it is not silently upgraded.

You can seed an exact pair without editing files. For an existing prompt, add `--refresh-models`; a conflicting override otherwise fails instead of silently changing models midway through the task.

```zsh
BUILDER_MODEL=ollama/minimax-m3:cloud \
REVIEWER_MODEL=ollama/glm-5.2:cloud \
zsh scripts/run_prompt_agents.zsh tiny-python-app prompt01
```

Exact overrides must be full `ollama/<model>:cloud` IDs. Family prefixes can be changed locally through `BUILDER_MODEL_FAMILY` and `REVIEWER_MODEL_FAMILY` in `project.local.env`. Alternate families are not benchmarked in this repo yet. OpenCode's separate `small_model` remains a stable bootstrap setting and is not coupled to prompt-family resolution.

For resolver diagnostics without launching an agent:

```zsh
python3 scripts/model_resolver.py status --session-dir agent-sessions/tiny-python-app/prompt01 --prompt-id prompt01
python3 scripts/model_resolver.py get --session-dir agent-sessions/tiny-python-app/prompt01 --prompt-id prompt01 --role builder
```

`status` emits compact JSON and `get` emits one exact model ID on stdout; warnings go to stderr. If resolution fails, run `zsh scripts/doctor.zsh`, inspect the error, correct the family or exact cloud override if necessary, and use `--refresh-models` only when you intentionally want to replace an existing prompt pair. Never hand-edit resolver-owned locks or caches.

OpenCode update checks are notification-only and can vary by installation method. The resolver never upgrades OpenCode automatically; after a human-managed upgrade, it re-verifies the existing prompt pair before the next run.

## Docs

- [Quickstart](docs/quickstart.md): install checks, local config, prompt creation, and first runs.
- [Architecture](docs/architecture.md): control workspace, product repo, session receipts, and human commit boundary.
- [Permission model](docs/permission-model.md): OpenCode permissions and reviewer write limits.
- [Session storage policy](docs/session-storage-policy.md): what stays local and what can be published.
- [Redaction checklist](docs/redaction-checklist.md): manual checks before publishing.
- [Screenshots policy](docs/screenshots-policy.md): safe screenshot handling.
- [MCP playbook](docs/mcp-playbook.md): tool and MCP hygiene.
- [Model matrix](docs/model-matrix.md): default builder/reviewer models and current limits.
- [Release checklist](docs/release-checklist.md): repeatable checks before tagging or publishing.

## Redaction Before Publishing

Scan the public pack:

```zsh
python3 scripts/validate_public_pack.py .
```

Scan a local session:

```zsh
python3 scripts/redact_sessions.py agent-sessions/project-slug/prompt01
```

Create redacted copies:

```zsh
python3 scripts/redact_sessions.py agent-sessions/project-slug/prompt01 --out tmp-redacted-session
```

Automated scanners are guardrails, not proof. Manually inspect markdown, scripts, examples, screenshots, shell snippets, sample env files, and generated output before publishing.

## Skills

Project skills live under `.opencode/skills/<skill-name>/SKILL.md`.

Included skills:

- `opencode-ollama-agent-guardrails`: builder/reviewer boundaries, no commits, no raw prompt publishing, no false success claims.
- `safe-session-redaction`: checks for local paths, secrets, emails, raw logs, screenshots, `.env` data, and private prompt history.
- `test-first-agent-loop`: requires validation evidence and honest failure reporting before signoff.

Skill names are lowercase and hyphen-separated. Each `SKILL.md` uses YAML frontmatter with `name` and `description`.

## What Not To Commit

- `project.local.env` or any `.env` file.
- Raw prompts from real work.
- Raw OpenCode logs, JSONL event streams, or session exports.
- Screenshots from private projects.
- Local absolute paths.
- Credentials, API keys, tokens, passwords, private keys, or provider auth files.
- Customer data, private issue titles, private repo URLs, or private roadmap details.
- Generated product artifacts from a private repository.

## Threat Model

This starter kit reduces common publishing and workflow risks:

- accidental prompt or session leaks;
- local path and username leaks;
- credentials in copied logs or sample env files;
- reviewer agents editing production code;
- agents claiming success without validation evidence;
- public screenshots showing private data;
- tools using broader access than the task needs.

It does not replace sandboxing, CI policy, secret scanning, code review, or human judgment. Treat every MCP server, shell command, browser capture, and generated artifact as a possible leak boundary.

## Roadmap

- Add optional CI checks for `validate_public_pack.py`.
- Add richer fake session examples for web apps and CLIs.
- Add adapter docs for common stacks.
- Add stricter reviewer-only file enforcement examples.
- Add optional integration with common secret scanners.

## Disclaimer

This project is not affiliated with OpenCode, Ollama, MiniMax, GLM, Anthropic, or OpenAI. Model names and product names belong to their respective owners.

## Public references

- OpenCode CLI: <https://opencode.ai/docs/cli/>
- OpenCode config: <https://opencode.ai/docs/config/>
- OpenCode agents: <https://opencode.ai/docs/agents/>
- OpenCode permissions: <https://opencode.ai/docs/permissions/>
- Ollama OpenCode integration: <https://docs.ollama.com/integrations/opencode>
- MiniMax M3 on Ollama: <https://ollama.com/library/minimax-m3>
- GLM-5.2 on Ollama: <https://ollama.com/library/glm-5.2>
