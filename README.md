# opencode-ollama-steroids

Stop vibe-coding blind.

A receipt-first OpenCode + Ollama multi-agent workflow for headless agent runs with builder/reviewer agents, local session receipts, skills, validation gates, screenshots policy, and redaction tooling.

This repo is a public-safe starter kit. Clone it beside or above a product repository, create prompt folders under `agent-sessions/`, run a builder agent, run a reviewer agent, keep receipts locally, and publish only sanitized templates or summaries.

It intentionally does not include private prompts, raw session logs, real screenshots, local machine paths, credentials, customer data, or generated private project artifacts.

## What this gives you

- `opencode.json` configured for two Ollama-backed OpenCode agents.
- `minimax-builder` for planning, implementation, validation, and implementation notes.
- `glm-reviewer` for strict plan, diff, test, screenshot, and security review.
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
scripts/doctor.zsh
```

Create a local project config:

```zsh
cp project.local.env.example project.local.env
```

Edit `project.local.env` for your own machine. Keep it uncommitted.

Create a prompt folder:

```zsh
scripts/new_prompt.zsh project-slug prompt01 "Add a health check, tests, docs, and reviewer signoff."
```

Run the builder:

```zsh
scripts/run_builder.zsh project-slug prompt01
```

Run the reviewer:

```zsh
scripts/run_reviewer.zsh project-slug prompt01
```

Or run both in sequence:

```zsh
scripts/run_prompt_agents.zsh project-slug prompt01
```

For repeated runs, start a local headless server:

```zsh
scripts/start_headless_server.zsh
scripts/run_builder.zsh project-slug prompt01 --attach http://localhost:4096
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
scripts/new_prompt.zsh <project-slug> <prompt-id> ["Task description"]
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
scripts/run_builder.zsh <project-slug> <prompt-id>
```

Reviewer:

```zsh
scripts/run_reviewer.zsh <project-slug> <prompt-id>
```

Both:

```zsh
scripts/run_prompt_agents.zsh <project-slug> <prompt-id>
```

With a local server:

```zsh
scripts/start_headless_server.zsh
scripts/run_prompt_agents.zsh <project-slug> <prompt-id> --attach http://localhost:4096
```

The scripts write raw logs under the session folder. Raw logs are ignored and must not be published.

## Docs

- [Quickstart](docs/quickstart.md): install checks, local config, prompt creation, and first runs.
- [Architecture](docs/architecture.md): control workspace, product repo, session receipts, and human commit boundary.
- [Permission model](docs/permission-model.md): OpenCode permissions and reviewer write limits.
- [Session storage policy](docs/session-storage-policy.md): what stays local and what can be published.
- [Redaction checklist](docs/redaction-checklist.md): manual checks before publishing.
- [Screenshots policy](docs/screenshots-policy.md): safe screenshot handling.
- [MCP playbook](docs/mcp-playbook.md): tool and MCP hygiene.
- [Model matrix](docs/model-matrix.md): default builder/reviewer models and current limits.

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
- GLM-5.1 on Ollama: <https://ollama.com/library/glm-5.1>
