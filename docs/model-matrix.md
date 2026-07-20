# Model Matrix

This starter kit is update-resilient within configured Ollama model families and pins the verified exact pair per prompt.

Default workflow:

- builder family: `minimax-m`; current bootstrap: `ollama/minimax-m3:cloud`
- reviewer family: `glm-`; current bootstrap: `ollama/glm-5.2:cloud`

## Selection contract

"Latest" means the highest stable numeric `:cloud` identifier in the refreshed Ollama catalog exposed by the installed OpenCode CLI and matching the configured family prefix. Components are compared numerically: `5.10` sorts above `5.2`, and `5.2.0` sorts above `5.2`. Preview, nonnumeric, malformed, non-cloud, other-provider, and unrelated-family IDs are ignored. This rule does not assert which model is globally newest, most recently published, or best.

Exact `BUILDER_MODEL` and `REVIEWER_MODEL` overrides must use the full `ollama/<model>:cloud` form. An explicit override is strict: parse, manifest, inference, or tool verification failure stops resolution. It never falls back to a different model. A conflicting override cannot silently replace an existing prompt lock; use `--refresh-models` to request that transaction explicitly.

## Verification and lock lifecycle

Before a new pair is committed, each exact ID must pass these checks through OpenCode's JSON event stream:

1. exact cloud-manifest readiness through Ollama;
2. a no-tools inference that returns only `OPENCODE_MODEL_SMOKE_OK`;
3. a tightly permissioned read of `.opencode/model-smoke/FIXTURE.txt` that returns only `OPENCODE_TOOL_SMOKE_OK:7F3A`.

Smoke inference can consume cloud quota. Raw responses are not persisted. The prompt lock records only provider, selectors, exact IDs, override context, source, toolchain/resolver versions, timestamps, catalog visibility, manifest readiness, runtime status, and per-stage pass status. Catalog visibility is only an inventory hint; manifest readiness and exact runtime/tool smokes are independent evidence. The separate schema-3 cache keeps last-known-good pairs isolated by provider, both family selectors, and both nullable exact overrides; the prompt-lock schema remains 2.

The lock is authoritative for every builder, reviewer, fix, signoff, and attached run. Normal reuse does not refresh the catalog. If the exact locked model is absent from a later catalog but its manifest remains runnable, the lock remains valid. A changed OpenCode, Ollama, or resolver verification version re-smokes the same pair without selecting a new one.

`--refresh-models` resolves and verifies both roles as one transaction. It atomically replaces the lock only after the entire candidate pair passes. On catalog, readiness, inference, tool, or cache-write failure, the old lock remains byte-for-byte unchanged. Per-prompt filesystem locking prevents concurrent first runs from racing or producing mixed pairs. Shared-cache writes use a separate short-lived global guard: each writer re-reads and merges the latest tested-model records and matching context before atomic replacement. Cache persistence precedes prompt-lock persistence.

## Fallback boundary

Last-known-good fallback is allowed only for catalog discovery or refresh failure, and only when family selectors and exact-override context match. The cached pair must still pass exact manifest readiness and any required toolchain-version re-smoke. There is no fallback after explicit override failure, manifest failure, inference failure, or tool failure. The resolver never crosses families and never removes `:cloud` to fetch a heavyweight local variant.

OpenCode's `small_model` is independent of this workflow and remains the checked-in stable bootstrap ID. The supported runners parse one immutable JSON result from `resolve`, make the selected role authoritative with `--model`, and reinforce both agent definitions from the same pair without changing `small_model`. The resolver's `get` subcommand is retained only for manual diagnostics. The reusable localhost server is deliberately model-agnostic.

When the installed OpenCode exposes `debug config` and `debug agent`, the resolver verifies that local runtime configuration resolves both agent names to the intended pair and fails clearly if higher-priority or managed configuration prevents that mapping. Attached correctness still rests on the invocation's explicit `--model`, not on client-side inline configuration reaching an existing server.

`autoupdate` is set to `"notify"`, but notification behavior can depend on the OpenCode installation method. The resolver never runs `opencode upgrade`; upgrades remain an explicit human action, followed by a same-pair compatibility re-smoke.

Keep the agent names stable unless you also update scripts and docs.
