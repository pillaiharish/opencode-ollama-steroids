#!/usr/bin/env python3
"""Resolve, verify, and pin Ollama model families for one prompt."""
from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROMPT_LOCK_SCHEMA_VERSION = 2
CACHE_SCHEMA_VERSION = 3
LEGACY_CACHE_SCHEMA_VERSION = 2
RESOLVER_VERSION = "2.1"
PROVIDER_ID = "ollama"
DEFAULT_BUILDER_FAMILY = "minimax-m"
DEFAULT_REVIEWER_FAMILY = "glm-"
MODEL_ID_RE = re.compile(r"^ollama/[a-z0-9][a-z0-9._/-]*:cloud$")
ANSI_RE = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")
INFERENCE_SENTINEL = "OPENCODE_MODEL_SMOKE_OK"
TOOL_SENTINEL = "OPENCODE_TOOL_SMOKE_OK:7F3A"


class ResolutionError(RuntimeError):
    """A safe, user-facing model resolution failure."""


class DiscoveryError(ResolutionError):
    """A catalog discovery failure that may use last-known-good state."""


class VerificationError(ResolutionError):
    """A readiness or smoke failure that must never silently fall back."""


@dataclass(frozen=True)
class ModelPair:
    builder: str
    reviewer: str


@dataclass(frozen=True)
class CommandResult:
    returncode: int
    stdout: str
    stderr: str


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


def strip_ansi(value: str) -> str:
    return ANSI_RE.sub("", value)


def version_key(value: str) -> tuple[int, ...]:
    return tuple(int(part) for part in value.split("."))


def validate_family(family: str) -> str:
    if not re.fullmatch(r"[a-z0-9][a-z0-9._-]*", family):
        raise ResolutionError(f"Invalid model family prefix: {family!r}")
    return family


def family_candidates(catalog: str, family: str) -> list[tuple[tuple[int, ...], str]]:
    validate_family(family)
    pattern = re.compile(
        rf"^ollama/{re.escape(family)}(?P<version>[0-9]+(?:\.[0-9]+)*):cloud$"
    )
    candidates: dict[str, tuple[int, ...]] = {}
    for raw_line in strip_ansi(catalog).splitlines():
        model = raw_line.strip()
        match = pattern.fullmatch(model)
        if match:
            candidates[model] = version_key(match.group("version"))
    return sorted(((key, model) for model, key in candidates.items()), reverse=True)


def select_latest(catalog: str, family: str) -> str:
    candidates = family_candidates(catalog, family)
    if not candidates:
        raise DiscoveryError(
            f"No stable Ollama cloud model matched family {family!r}. "
            "Set an exact model override or update the family prefix."
        )
    return candidates[0][1]


def validate_model_id(model: str, label: str) -> str:
    if not MODEL_ID_RE.fullmatch(model):
        raise ResolutionError(
            f"Invalid {label} model ID {model!r}; expected a strict Ollama Cloud ID such as "
            "ollama/family-version:cloud. Local and non-cloud overrides are not allowed."
        )
    return model


def runtime_config(pair: ModelPair) -> str:
    return json.dumps(
        {
            "model": pair.builder,
            "agent": {
                "minimax-builder": {"model": pair.builder},
                "glm-reviewer": {"model": pair.reviewer},
            },
        },
        separators=(",", ":"),
        sort_keys=True,
    )


def atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    handle = tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
        delete=False,
    )
    temporary = Path(handle.name)
    try:
        with handle:
            json.dump(payload, handle, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def load_json(path: Path, label: str, tolerate_corrupt: bool = False) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        if tolerate_corrupt:
            print(f"warning: ignoring corrupt {label}: {exc}", file=sys.stderr)
            return None
        raise ResolutionError(f"Cannot read {label}: {exc}") from exc
    if not isinstance(value, dict):
        if tolerate_corrupt:
            print(f"warning: ignoring invalid {label}", file=sys.stderr)
            return None
        raise ResolutionError(f"Invalid {label}: expected a JSON object")
    return value


class Resolver:
    def __init__(
        self,
        workspace: Path,
        state_root: Path,
        opencode_bin: str = "opencode",
        ollama_bin: str = "ollama",
        command_timeout: int = 60,
    ) -> None:
        self.workspace = workspace
        self.state_root = state_root if state_root.is_absolute() else workspace / state_root
        self.cache_path = self.state_root / ".model-cache.json"
        self.cache_guard_path = self.state_root / ".model-cache.lock"
        self.opencode_bin = opencode_bin
        self.ollama_bin = ollama_bin
        self.command_timeout = command_timeout

    def command(
        self,
        args: list[str],
        env: dict[str, str] | None = None,
    ) -> CommandResult:
        try:
            completed = subprocess.run(
                args,
                cwd=self.workspace,
                env=env,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=self.command_timeout,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise ResolutionError(f"Could not run {Path(args[0]).name}: {exc}") from exc
        return CommandResult(completed.returncode, completed.stdout, completed.stderr)

    def tool_version(self, binary: str) -> str:
        result = self.command([binary, "--version"])
        if result.returncode != 0:
            return "unknown"
        text = strip_ansi(result.stdout or result.stderr).strip()
        return text.splitlines()[0] if text else "unknown"

    def refresh_catalog(self) -> str:
        result = self.command([self.opencode_bin, "models", "ollama", "--refresh"])
        if result.returncode != 0:
            raise DiscoveryError("OpenCode could not refresh the Ollama model catalog")
        catalog = result.stdout
        if "ollama/" not in strip_ansi(catalog):
            raise DiscoveryError("OpenCode returned an empty Ollama model catalog")
        return catalog

    @staticmethod
    def remote_model_id(model: str) -> str:
        return model.removeprefix("ollama/")

    def model_is_available(self, model: str) -> bool:
        result = self.command([self.ollama_bin, "show", self.remote_model_id(model)])
        return result.returncode == 0

    def ensure_available(self, model: str) -> None:
        validate_model_id(model, "cloud")
        if self.model_is_available(model):
            return
        result = self.command([self.ollama_bin, "pull", self.remote_model_id(model)])
        if result.returncode != 0 or not self.model_is_available(model):
            raise VerificationError(f"Ollama could not make cloud model {model!r} available")

    @staticmethod
    def run_events(output: str) -> list[dict[str, Any]] | None:
        events: list[dict[str, Any]] = []
        for line in strip_ansi(output).splitlines():
            if not line.strip():
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                return None
            if not isinstance(event, dict):
                return None
            events.append(event)
        return events or None

    @staticmethod
    def exact_structured_response(output: str, expected: str) -> bool:
        events = Resolver.run_events(output)
        if events is None:
            return False
        text_parts = [
            part.get("text")
            for event in events
            if event.get("type") == "text"
            and isinstance((part := event.get("part")), dict)
            and part.get("type") == "text"
            and isinstance(part.get("text"), str)
        ]
        return bool(text_parts) and "".join(text_parts).strip() == expected

    def completed_fixture_read(self, output: str) -> bool:
        events = Resolver.run_events(output)
        if events is None:
            return False
        tool_parts = [
            part
            for event in events
            if event.get("type") == "tool_use"
            and isinstance((part := event.get("part")), dict)
            and part.get("type") == "tool"
        ]
        if len(tool_parts) != 1 or tool_parts[0].get("tool") != "read":
            return False
        state = tool_parts[0].get("state")
        inputs = state.get("input") if isinstance(state, dict) else None
        output_text = state.get("output") if isinstance(state, dict) else None
        file_path = inputs.get("filePath") if isinstance(inputs, dict) else None
        expected_relative = Path(".opencode/model-smoke/FIXTURE.txt")
        path_matches = False
        if isinstance(file_path, str):
            reported_path = Path(file_path)
            path_matches = (
                reported_path == expected_relative
                if not reported_path.is_absolute()
                else reported_path.resolve() == (self.workspace / expected_relative).resolve()
            )
        return (
            isinstance(state, dict)
            and state.get("status") == "completed"
            and isinstance(inputs, dict)
            and path_matches
            and isinstance(output_text, str)
            and "7F3A" in output_text
        )

    @staticmethod
    def parse_json_output(result: CommandResult, label: str) -> dict[str, Any]:
        try:
            payload = json.loads(strip_ansi(result.stdout))
        except json.JSONDecodeError as exc:
            raise VerificationError(
                f"OpenCode {label} returned malformed configuration output"
            ) from exc
        if not isinstance(payload, dict):
            raise VerificationError(f"OpenCode {label} returned an invalid configuration object")
        return payload

    def validate_runtime_mapping(self, pair: ModelPair) -> None:
        """Confirm local runtime config when the installed OpenCode exposes debug commands."""
        environment = os.environ.copy()
        environment["OPENCODE_CONFIG_CONTENT"] = runtime_config(pair)
        config_result = self.command([self.opencode_bin, "debug", "config"], env=environment)
        if config_result.returncode != 0:
            print(
                "warning: installed OpenCode does not expose usable debug config validation; "
                "per-run --model remains authoritative",
                file=sys.stderr,
            )
            return

        config = self.parse_json_output(config_result, "debug config")
        agents = config.get("agent")
        intended = {
            "minimax-builder": pair.builder,
            "glm-reviewer": pair.reviewer,
        }
        if config.get("model") != pair.builder or not isinstance(agents, dict):
            raise VerificationError(
                "OpenCode debug config shows that managed or higher-priority configuration "
                "prevented the intended resolved model mapping"
            )
        for agent_name, expected_model in intended.items():
            agent_config = agents.get(agent_name)
            if not isinstance(agent_config, dict) or agent_config.get("model") != expected_model:
                raise VerificationError(
                    "OpenCode debug config shows that managed or higher-priority configuration "
                    f"prevented the intended {agent_name} model mapping"
                )
            agent_result = self.command(
                [self.opencode_bin, "debug", "agent", agent_name], env=environment
            )
            if agent_result.returncode != 0:
                raise VerificationError(f"OpenCode could not inspect resolved agent {agent_name!r}")
            agent_payload = self.parse_json_output(agent_result, f"debug agent {agent_name}")
            model_payload = agent_payload.get("model")
            expected_provider, expected_id = expected_model.split("/", 1)
            if not isinstance(model_payload, dict) or (
                model_payload.get("providerID") != expected_provider
                or model_payload.get("modelID") != expected_id
            ):
                raise VerificationError(
                    "OpenCode debug agent shows that managed or higher-priority configuration "
                    f"prevented the intended {agent_name} model mapping"
                )

    def smoke_model(self, model: str, pair: ModelPair) -> None:
        environment = os.environ.copy()
        environment["OPENCODE_CONFIG_CONTENT"] = runtime_config(pair)
        inference = self.command(
            [
                self.opencode_bin,
                "run",
                "--format",
                "json",
                "--model",
                model,
                "--agent",
                "model-inference-smoke",
                "--dir",
                ".",
                "Return exactly: OPENCODE_MODEL_SMOKE_OK",
            ],
            env=environment,
        )
        if inference.returncode != 0 or not self.exact_structured_response(
            inference.stdout, INFERENCE_SENTINEL
        ):
            raise VerificationError(f"OpenCode inference smoke failed for {model!r}")

        tool = self.command(
            [
                self.opencode_bin,
                "run",
                "--format",
                "json",
                "--model",
                model,
                "--agent",
                "model-tool-smoke",
                "--dir",
                ".",
                "Read .opencode/model-smoke/FIXTURE.txt and return exactly: "
                "OPENCODE_TOOL_SMOKE_OK:7F3A",
            ],
            env=environment,
        )
        if (
            tool.returncode != 0
            or not self.completed_fixture_read(tool.stdout)
            or not self.exact_structured_response(tool.stdout, TOOL_SENTINEL)
        ):
            raise VerificationError(f"OpenCode controlled tool smoke failed for {model!r}")

    @staticmethod
    def empty_cache() -> dict[str, Any]:
        return {
            "schema_version": CACHE_SCHEMA_VERSION,
            "resolver_version": RESOLVER_VERSION,
            "tested_models": {},
            "last_good_by_context": {},
        }

    @staticmethod
    def parsed_timestamp(value: Any) -> datetime | None:
        if not isinstance(value, str):
            return None
        try:
            parsed = datetime.fromisoformat(value)
        except ValueError:
            return None
        return parsed if parsed.tzinfo is not None else None

    @staticmethod
    def context_payload(
        builder_family: str,
        reviewer_family: str,
        builder_model: str | None,
        reviewer_model: str | None,
    ) -> dict[str, Any]:
        return {
            "provider": PROVIDER_ID,
            "builder_family": validate_family(builder_family),
            "reviewer_family": validate_family(reviewer_family),
            "builder_override": builder_model,
            "reviewer_override": reviewer_model,
        }

    @staticmethod
    def context_key(
        builder_family: str,
        reviewer_family: str,
        builder_model: str | None,
        reviewer_model: str | None,
    ) -> str:
        payload = Resolver.context_payload(
            builder_family,
            reviewer_family,
            builder_model,
            reviewer_model,
        )
        canonical = json.dumps(payload, separators=(",", ":"), sort_keys=True)
        return "sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    @staticmethod
    def sanitized_tested_record(model: str, record: Any) -> dict[str, Any] | None:
        if not isinstance(record, dict):
            return None
        try:
            validate_model_id(model, "cached tested")
        except ResolutionError:
            return None
        required_strings = (
            "opencode_version",
            "ollama_version",
            "resolver_version",
            "verified_at",
        )
        if (
            record.get("provider") != PROVIDER_ID
            or any(not isinstance(record.get(field), str) for field in required_strings)
            or Resolver.parsed_timestamp(record.get("verified_at")) is None
            or record.get("runtime_status") != "passed"
            or record.get("inference_smoke") != "passed"
            or record.get("tool_smoke") != "passed"
        ):
            return None
        return {
            "provider": PROVIDER_ID,
            "opencode_version": record["opencode_version"],
            "ollama_version": record["ollama_version"],
            "resolver_version": record["resolver_version"],
            "runtime_status": "passed",
            "inference_smoke": "passed",
            "tool_smoke": "passed",
            "verified_at": record["verified_at"],
        }

    @staticmethod
    def sanitized_last_good(record: Any) -> tuple[str, dict[str, Any]] | None:
        if not isinstance(record, dict) or record.get("provider") != PROVIDER_ID:
            return None
        families = record.get("families")
        overrides = record.get("overrides")
        toolchain = record.get("toolchain")
        builder_record = record.get("builder")
        reviewer_record = record.get("reviewer")
        if not all(
            isinstance(value, dict)
            for value in (families, overrides, toolchain, builder_record, reviewer_record)
        ):
            return None
        builder_family = families.get("builder")
        reviewer_family = families.get("reviewer")
        if not isinstance(builder_family, str) or not isinstance(reviewer_family, str):
            return None
        try:
            validate_family(builder_family)
            validate_family(reviewer_family)
        except ResolutionError:
            return None
        builder_override = overrides.get("builder")
        reviewer_override = overrides.get("reviewer")
        try:
            if builder_override is not None:
                if not isinstance(builder_override, str):
                    return None
                builder_override = validate_model_id(builder_override, "cached builder override")
            if reviewer_override is not None:
                if not isinstance(reviewer_override, str):
                    return None
                reviewer_override = validate_model_id(
                    reviewer_override, "cached reviewer override"
                )
            pair = ModelPair(
                validate_model_id(builder_record.get("exact_id", ""), "cached builder"),
                validate_model_id(reviewer_record.get("exact_id", ""), "cached reviewer"),
            )
        except ResolutionError:
            return None
        if not Resolver.exact_overrides_match(pair, builder_override, reviewer_override):
            return None
        if (
            builder_record.get("source") == "exact_override" and builder_override is None
        ) or (
            reviewer_record.get("source") == "exact_override" and reviewer_override is None
        ):
            return None
        if any(
            role.get("runtime_status") != "passed"
            or role.get("inference_smoke") != "passed"
            or role.get("tool_smoke") != "passed"
            for role in (builder_record, reviewer_record)
        ):
            return None
        if not all(
            isinstance(toolchain.get(field), str) for field in ("opencode", "ollama")
        ):
            return None
        verified_at = record.get("verified_at")
        if Resolver.parsed_timestamp(verified_at) is None:
            return None
        key = Resolver.context_key(
            builder_family,
            reviewer_family,
            builder_override,
            reviewer_override,
        )
        sanitized = {
            "provider": PROVIDER_ID,
            "families": {"builder": builder_family, "reviewer": reviewer_family},
            "overrides": {"builder": builder_override, "reviewer": reviewer_override},
            "toolchain": {
                "opencode": toolchain["opencode"],
                "ollama": toolchain["ollama"],
            },
            "verified_at": verified_at,
            "builder": {
                "exact_id": pair.builder,
                "runtime_status": "passed",
                "inference_smoke": "passed",
                "tool_smoke": "passed",
            },
            "reviewer": {
                "exact_id": pair.reviewer,
                "runtime_status": "passed",
                "inference_smoke": "passed",
                "tool_smoke": "passed",
            },
        }
        return key, sanitized

    @staticmethod
    def normalize_cache(document: dict[str, Any] | None) -> dict[str, Any]:
        normalized = Resolver.empty_cache()
        if not isinstance(document, dict):
            return normalized

        tested = document.get("tested_models")
        dropped_tested = 0
        if isinstance(tested, dict):
            for model, record in tested.items():
                if not isinstance(model, str):
                    dropped_tested += 1
                    continue
                sanitized = Resolver.sanitized_tested_record(model, record)
                if sanitized is None:
                    dropped_tested += 1
                    continue
                normalized["tested_models"][model] = sanitized
        elif tested is not None:
            dropped_tested = 1
        if dropped_tested:
            print(
                f"warning: ignored {dropped_tested} invalid tested-model cache record(s)",
                file=sys.stderr,
            )

        schema = document.get("schema_version")
        if schema == CACHE_SCHEMA_VERSION:
            contexts = document.get("last_good_by_context")
            if isinstance(contexts, dict):
                for stored_key, record in contexts.items():
                    migrated = Resolver.sanitized_last_good(record)
                    if migrated is None or migrated[0] != stored_key:
                        print(
                            "warning: ignored invalid context-indexed last-known-good record",
                            file=sys.stderr,
                        )
                        continue
                    normalized["last_good_by_context"][stored_key] = migrated[1]
            elif contexts is not None:
                print("warning: ignored invalid last-known-good context map", file=sys.stderr)
        elif schema == LEGACY_CACHE_SCHEMA_VERSION:
            legacy = document.get("last_good")
            if legacy is not None:
                migrated = Resolver.sanitized_last_good(legacy)
                if migrated is None:
                    print(
                        "warning: ignored invalid legacy last-known-good cache record",
                        file=sys.stderr,
                    )
                else:
                    normalized["last_good_by_context"][migrated[0]] = migrated[1]
        else:
            print(
                "warning: unsupported model cache schema; preserving only valid tested models",
                file=sys.stderr,
            )
        return normalized

    def read_cache_snapshot(self) -> dict[str, Any]:
        self.state_root.mkdir(parents=True, exist_ok=True)
        try:
            with self.cache_guard_path.open("a+", encoding="utf-8") as guard:
                fcntl.flock(guard.fileno(), fcntl.LOCK_EX)
                document = load_json(
                    self.cache_path,
                    "model cache",
                    tolerate_corrupt=True,
                )
                return self.normalize_cache(document)
        except OSError as exc:
            raise ResolutionError(f"Could not read the shared model cache: {exc}") from exc

    @staticmethod
    def tested_model_updates(
        before: dict[str, Any], after: dict[str, Any]
    ) -> dict[str, dict[str, Any]]:
        before_tested = before.get("tested_models", {})
        after_tested = after.get("tested_models", {})
        if not isinstance(before_tested, dict) or not isinstance(after_tested, dict):
            return {}
        return {
            model: record
            for model, record in after_tested.items()
            if isinstance(model, str)
            and isinstance(record, dict)
            and before_tested.get(model) != record
        }

    def persist_cache_transaction(
        self,
        tested_updates: dict[str, dict[str, Any]],
        last_good: dict[str, Any] | None,
    ) -> dict[str, Any]:
        try:
            with self.cache_guard_path.open("a+", encoding="utf-8") as guard:
                fcntl.flock(guard.fileno(), fcntl.LOCK_EX)
                latest = self.normalize_cache(
                    load_json(self.cache_path, "model cache", tolerate_corrupt=True)
                )
                latest_tested = latest["tested_models"]
                for model, incoming in tested_updates.items():
                    sanitized = self.sanitized_tested_record(model, incoming)
                    if sanitized is None:
                        raise ResolutionError(
                            f"Refusing to persist invalid tested-model record for {model!r}"
                        )
                    existing = latest_tested.get(model)
                    incoming_time = self.parsed_timestamp(sanitized["verified_at"])
                    existing_time = (
                        self.parsed_timestamp(existing.get("verified_at"))
                        if isinstance(existing, dict)
                        else None
                    )
                    if existing_time is None or (
                        incoming_time is not None and incoming_time > existing_time
                    ):
                        latest_tested[model] = sanitized

                if last_good is not None:
                    migrated = self.sanitized_last_good(last_good)
                    if migrated is None:
                        raise ResolutionError(
                            "Refusing to persist an invalid last-known-good context"
                        )
                    latest["last_good_by_context"][migrated[0]] = migrated[1]

                latest["schema_version"] = CACHE_SCHEMA_VERSION
                latest["resolver_version"] = RESOLVER_VERSION
                atomic_write_json(self.cache_path, latest)
                return latest
        except ResolutionError:
            raise
        except OSError as exc:
            raise ResolutionError(
                f"Could not persist the shared model cache; the prompt lock was not changed: {exc}"
            ) from exc

    @staticmethod
    def persist_prompt_lock(path: Path, payload: dict[str, Any]) -> None:
        try:
            atomic_write_json(path, payload)
        except OSError as exc:
            raise ResolutionError(f"Could not persist the prompt model lock: {exc}") from exc

    @staticmethod
    def tested_for_toolchain(
        cache: dict[str, Any], model: str, opencode_version: str, ollama_version: str
    ) -> bool:
        tested = cache.get("tested_models", {})
        record = tested.get(model) if isinstance(tested, dict) else None
        return (
            isinstance(record, dict)
            and record.get("provider") == PROVIDER_ID
            and record.get("opencode_version") == opencode_version
            and record.get("ollama_version") == ollama_version
            and record.get("resolver_version") == RESOLVER_VERSION
            and record.get("runtime_status") == "passed"
            and record.get("inference_smoke") == "passed"
            and record.get("tool_smoke") == "passed"
        )

    @staticmethod
    def mark_tested(
        cache: dict[str, Any], model: str, opencode_version: str, ollama_version: str
    ) -> None:
        tested = cache.setdefault("tested_models", {})
        if not isinstance(tested, dict):
            tested = {}
            cache["tested_models"] = tested
        tested[model] = {
            "provider": PROVIDER_ID,
            "opencode_version": opencode_version,
            "ollama_version": ollama_version,
            "resolver_version": RESOLVER_VERSION,
            "runtime_status": "passed",
            "inference_smoke": "passed",
            "tool_smoke": "passed",
            "verified_at": utc_now(),
        }

    def verify_pair(
        self,
        pair: ModelPair,
        cache: dict[str, Any],
        opencode_version: str,
        ollama_version: str,
        force_smoke: bool = False,
    ) -> None:
        self.ensure_available(pair.builder)
        self.ensure_available(pair.reviewer)
        self.validate_runtime_mapping(pair)
        models = tuple(dict.fromkeys((pair.builder, pair.reviewer)))
        needs_smoke = force_smoke or any(
            not self.tested_for_toolchain(cache, model, opencode_version, ollama_version)
            for model in models
        )
        if needs_smoke:
            print(
                "warning: verifying unseen or stale Ollama Cloud models may consume provider quota",
                file=sys.stderr,
            )
        for model in models:
            if force_smoke or not self.tested_for_toolchain(
                cache, model, opencode_version, ollama_version
            ):
                self.smoke_model(model, pair)
                self.mark_tested(cache, model, opencode_version, ollama_version)

    @staticmethod
    def cache_pair(
        cache: dict[str, Any],
        builder_family: str,
        reviewer_family: str,
        builder_model: str | None,
        reviewer_model: str | None,
    ) -> ModelPair | None:
        contexts = cache.get("last_good_by_context")
        if not isinstance(contexts, dict):
            return None
        key = Resolver.context_key(
            builder_family,
            reviewer_family,
            builder_model,
            reviewer_model,
        )
        record = contexts.get(key)
        if not isinstance(record, dict):
            return None
        validated = Resolver.sanitized_last_good(record)
        if validated is None or validated[0] != key:
            return None
        record = validated[1]
        families = record.get("families")
        overrides = record.get("overrides")
        if not isinstance(families, dict) or not isinstance(overrides, dict):
            return None
        if families.get("builder") != builder_family or families.get("reviewer") != reviewer_family:
            return None
        if overrides.get("builder") != builder_model or overrides.get("reviewer") != reviewer_model:
            return None
        builder_record = record.get("builder")
        reviewer_record = record.get("reviewer")
        if not isinstance(builder_record, dict) or not isinstance(reviewer_record, dict):
            return None
        if any(
            role.get("runtime_status") != "passed"
            or role.get("inference_smoke") != "passed"
            or role.get("tool_smoke") != "passed"
            for role in (builder_record, reviewer_record)
        ):
            return None
        builder = builder_record.get("exact_id")
        reviewer = reviewer_record.get("exact_id")
        if not isinstance(builder, str) or not isinstance(reviewer, str):
            return None
        try:
            return ModelPair(
                validate_model_id(builder, "cached builder"),
                validate_model_id(reviewer, "cached reviewer"),
            )
        except ResolutionError:
            return None

    @staticmethod
    def exact_overrides_match(pair: ModelPair, builder_model: str | None, reviewer_model: str | None) -> bool:
        return (not builder_model or builder_model == pair.builder) and (
            not reviewer_model or reviewer_model == pair.reviewer
        )

    def use_last_good(
        self,
        cache: dict[str, Any],
        builder_family: str,
        reviewer_family: str,
        builder_model: str | None,
        reviewer_model: str | None,
        opencode_version: str,
        ollama_version: str,
        reason: str,
    ) -> ModelPair:
        pair = self.cache_pair(
            cache,
            builder_family,
            reviewer_family,
            builder_model,
            reviewer_model,
        )
        if pair is None or not self.exact_overrides_match(pair, builder_model, reviewer_model):
            raise ResolutionError(f"{reason}; no matching last-known-good model pair is available")
        print(f"WARNING: {reason}; using a compatible last-known-good prompt model pair", file=sys.stderr)
        self.verify_pair(pair, cache, opencode_version, ollama_version)
        return pair

    @staticmethod
    def locked_pair(
        lock: dict[str, Any],
        project_slug: str,
        prompt_id: str,
        builder_family: str,
        reviewer_family: str,
        builder_model: str | None,
        reviewer_model: str | None,
    ) -> ModelPair:
        schema = lock.get("schema_version")
        if schema == 1:
            locked_builder_family = lock.get("builder_family")
            locked_reviewer_family = lock.get("reviewer_family")
            builder_exact = lock.get("builder_model")
            reviewer_exact = lock.get("reviewer_model")
        elif schema == PROMPT_LOCK_SCHEMA_VERSION:
            if (
                lock.get("provider") != PROVIDER_ID
                or lock.get("project_slug") != project_slug
                or lock.get("prompt_id") != prompt_id
            ):
                raise ResolutionError(
                    "Prompt model lock identity or provider is invalid; rerun with --refresh-models"
                )
            builder_record = lock.get("builder")
            reviewer_record = lock.get("reviewer")
            if not isinstance(builder_record, dict) or not isinstance(reviewer_record, dict):
                raise ResolutionError("Prompt model lock is incomplete; rerun with --refresh-models")
            locked_builder_family = builder_record.get("family")
            locked_reviewer_family = reviewer_record.get("family")
            builder_exact = builder_record.get("exact_id")
            reviewer_exact = reviewer_record.get("exact_id")
        else:
            raise ResolutionError("Unsupported prompt model lock schema; rerun with --refresh-models")
        if locked_builder_family != builder_family or locked_reviewer_family != reviewer_family:
            raise ResolutionError("Prompt model families differ from the lock; rerun with --refresh-models")
        pair = ModelPair(
            validate_model_id(str(builder_exact or ""), "locked builder"),
            validate_model_id(str(reviewer_exact or ""), "locked reviewer"),
        )
        if not Resolver.exact_overrides_match(pair, builder_model, reviewer_model):
            raise ResolutionError("Exact model override conflicts with the prompt lock; rerun with --refresh-models")
        return pair

    @staticmethod
    def lock_verification_current(
        lock: dict[str, Any], opencode_version: str, ollama_version: str
    ) -> bool:
        if lock.get("schema_version") != PROMPT_LOCK_SCHEMA_VERSION:
            return False
        if lock.get("resolver_version") != RESOLVER_VERSION:
            return False
        toolchain = lock.get("toolchain")
        builder = lock.get("builder")
        reviewer = lock.get("reviewer")
        return (
            isinstance(toolchain, dict)
            and toolchain.get("opencode") == opencode_version
            and toolchain.get("ollama") == ollama_version
            and all(
                isinstance(role, dict)
                and role.get("manifest_ready") is True
                and role.get("runtime_status") == "passed"
                and role.get("inference_smoke") == "passed"
                and role.get("tool_smoke") == "passed"
                for role in (builder, reviewer)
            )
        )

    @staticmethod
    def catalog_ids(catalog: str) -> set[str]:
        return {
            line.strip()
            for line in strip_ansi(catalog).splitlines()
            if MODEL_ID_RE.fullmatch(line.strip())
        }

    @staticmethod
    def role_payload(
        family: str,
        exact_id: str,
        source: str,
        catalog_models: set[str] | None,
    ) -> dict[str, Any]:
        return {
            "family": family,
            "exact_id": exact_id,
            "manifest_id": Resolver.remote_model_id(exact_id),
            "source": source,
            "catalog_visible": None if catalog_models is None else exact_id in catalog_models,
            "manifest_ready": True,
            "runtime_status": "passed",
            "inference_smoke": "passed",
            "tool_smoke": "passed",
        }

    @staticmethod
    def build_lock(
        project_slug: str,
        prompt_id: str,
        pair: ModelPair,
        builder_family: str,
        reviewer_family: str,
        builder_source: str,
        reviewer_source: str,
        resolution_source: str,
        opencode_version: str,
        ollama_version: str,
        catalog_models: set[str] | None,
        builder_override: str | None,
        reviewer_override: str | None,
    ) -> dict[str, Any]:
        return {
            "schema_version": PROMPT_LOCK_SCHEMA_VERSION,
            "resolver_version": RESOLVER_VERSION,
            "project_slug": project_slug,
            "prompt_id": prompt_id,
            "resolved_at": utc_now(),
            "resolution_source": resolution_source,
            "provider": PROVIDER_ID,
            "toolchain": {
                "opencode": opencode_version,
                "ollama": ollama_version,
            },
            "override_context": {
                "builder": builder_override,
                "reviewer": reviewer_override,
            },
            "builder": Resolver.role_payload(
                builder_family, pair.builder, builder_source, catalog_models
            ),
            "reviewer": Resolver.role_payload(
                reviewer_family, pair.reviewer, reviewer_source, catalog_models
            ),
        }

    @staticmethod
    def build_last_good(
        pair: ModelPair,
        builder_family: str,
        reviewer_family: str,
        builder_model: str | None,
        reviewer_model: str | None,
        opencode_version: str,
        ollama_version: str,
    ) -> dict[str, Any]:
        verified_at = utc_now()
        return {
            "provider": PROVIDER_ID,
            "families": {"builder": builder_family, "reviewer": reviewer_family},
            "overrides": {"builder": builder_model, "reviewer": reviewer_model},
            "toolchain": {"opencode": opencode_version, "ollama": ollama_version},
            "verified_at": verified_at,
            "builder": {
                "exact_id": pair.builder,
                "runtime_status": "passed",
                "inference_smoke": "passed",
                "tool_smoke": "passed",
            },
            "reviewer": {
                "exact_id": pair.reviewer,
                "runtime_status": "passed",
                "inference_smoke": "passed",
                "tool_smoke": "passed",
            },
        }

    @staticmethod
    def locked_override_context(
        lock: dict[str, Any], pair: ModelPair
    ) -> tuple[str | None, str | None] | None:
        if lock.get("schema_version") != PROMPT_LOCK_SCHEMA_VERSION:
            return None
        context = lock.get("override_context")
        if not isinstance(context, dict):
            raise ResolutionError(
                "Prompt model lock override context is invalid; rerun with --refresh-models"
            )
        builder_override = context.get("builder")
        reviewer_override = context.get("reviewer")
        try:
            if builder_override is not None:
                if not isinstance(builder_override, str):
                    raise ResolutionError("invalid builder override type")
                builder_override = validate_model_id(
                    builder_override, "locked builder override"
                )
            if reviewer_override is not None:
                if not isinstance(reviewer_override, str):
                    raise ResolutionError("invalid reviewer override type")
                reviewer_override = validate_model_id(
                    reviewer_override, "locked reviewer override"
                )
        except ResolutionError as exc:
            raise ResolutionError(
                "Prompt model lock override context is invalid; rerun with --refresh-models"
            ) from exc
        if not Resolver.exact_overrides_match(pair, builder_override, reviewer_override):
            raise ResolutionError(
                "Prompt model lock override context conflicts with its exact pair; "
                "rerun with --refresh-models"
            )
        builder_record = lock.get("builder")
        reviewer_record = lock.get("reviewer")
        if (
            isinstance(builder_record, dict)
            and builder_record.get("source") == "exact_override"
            and builder_override is None
        ) or (
            isinstance(reviewer_record, dict)
            and reviewer_record.get("source") == "exact_override"
            and reviewer_override is None
        ):
            raise ResolutionError(
                "Prompt model lock override context is incomplete; rerun with --refresh-models"
            )
        return builder_override, reviewer_override

    def resolve(
        self,
        session_dir: Path,
        project_slug: str,
        prompt_id: str,
        builder_family: str,
        reviewer_family: str,
        builder_model: str | None,
        reviewer_model: str | None,
        refresh_models: bool,
    ) -> tuple[ModelPair, dict[str, Any]]:
        builder_family = validate_family(builder_family)
        reviewer_family = validate_family(reviewer_family)
        builder_model = validate_model_id(builder_model, "builder") if builder_model else None
        reviewer_model = validate_model_id(reviewer_model, "reviewer") if reviewer_model else None
        session_dir = session_dir if session_dir.is_absolute() else self.workspace / session_dir
        self.state_root.mkdir(parents=True, exist_ok=True)
        session_dir.mkdir(parents=True, exist_ok=True)
        lock_path = session_dir / f"{prompt_id.upper()}_MODELS.json"
        guard_path = session_dir / f".{prompt_id.upper()}_MODELS.lock"

        with guard_path.open("a+", encoding="utf-8") as guard:
            fcntl.flock(guard.fileno(), fcntl.LOCK_EX)
            had_lock = lock_path.exists()
            existing_lock = load_json(
                lock_path,
                "prompt model lock",
                tolerate_corrupt=refresh_models,
            )
            opencode_version = self.tool_version(self.opencode_bin)
            ollama_version = self.tool_version(self.ollama_bin)

            if existing_lock is not None and not refresh_models:
                pair = self.locked_pair(
                    existing_lock,
                    project_slug,
                    prompt_id,
                    builder_family,
                    reviewer_family,
                    builder_model,
                    reviewer_model,
                )
                self.ensure_available(pair.builder)
                self.ensure_available(pair.reviewer)
                if self.lock_verification_current(
                    existing_lock, opencode_version, ollama_version
                ):
                    return pair, existing_lock
                cache = self.read_cache_snapshot()
                cache_before = {
                    "tested_models": dict(cache.get("tested_models", {})),
                }
                print(
                    "warning: prompt model verification is stale for the installed toolchain; "
                    "re-verifying the locked exact pair without catalog refresh",
                    file=sys.stderr,
                )
                self.verify_pair(
                    pair,
                    cache,
                    opencode_version,
                    ollama_version,
                    force_smoke=True,
                )
                locked_overrides = self.locked_override_context(existing_lock, pair)
                if locked_overrides is None:
                    lock_builder_override = builder_model
                    lock_reviewer_override = reviewer_model
                    last_good = None
                else:
                    lock_builder_override, lock_reviewer_override = locked_overrides
                    last_good = self.build_last_good(
                        pair,
                        builder_family,
                        reviewer_family,
                        lock_builder_override,
                        lock_reviewer_override,
                        opencode_version,
                        ollama_version,
                    )
                upgraded_lock = self.build_lock(
                    project_slug,
                    prompt_id,
                    pair,
                    builder_family,
                    reviewer_family,
                    "prompt_lock",
                    "prompt_lock",
                    "prompt_lock_reverified",
                    opencode_version,
                    ollama_version,
                    None,
                    lock_builder_override,
                    lock_reviewer_override,
                )
                self.persist_cache_transaction(
                    self.tested_model_updates(cache_before, cache),
                    last_good,
                )
                self.persist_prompt_lock(lock_path, upgraded_lock)
                return pair, upgraded_lock

            cache = self.read_cache_snapshot()
            cache_before = {
                "tested_models": dict(cache.get("tested_models", {})),
            }
            catalog = ""
            catalog_models: set[str] | None = None
            builder_source = "exact_override" if builder_model else "family"
            reviewer_source = "exact_override" if reviewer_model else "family"
            resolution_source = (
                "exact_override"
                if builder_model and reviewer_model
                else "mixed"
                if builder_model or reviewer_model
                else "refreshed_catalog"
            )
            try:
                if builder_model is None or reviewer_model is None:
                    catalog = self.refresh_catalog()
                    catalog_models = self.catalog_ids(catalog)
                pair = ModelPair(
                    builder_model or select_latest(catalog, builder_family),
                    reviewer_model or select_latest(catalog, reviewer_family),
                )
            except DiscoveryError as exc:
                if had_lock:
                    raise ResolutionError(
                        f"Model refresh failed; the existing prompt lock was not changed: {exc}"
                    ) from exc
                pair = self.use_last_good(
                    cache,
                    builder_family,
                    reviewer_family,
                    builder_model,
                    reviewer_model,
                    opencode_version,
                    ollama_version,
                    str(exc),
                )
                builder_source = "last_known_good"
                reviewer_source = "last_known_good"
                resolution_source = "last_known_good"
                catalog_models = None
            else:
                try:
                    self.verify_pair(pair, cache, opencode_version, ollama_version)
                except VerificationError as exc:
                    if had_lock:
                        raise ResolutionError(
                            f"Model refresh verification failed; the existing prompt lock was not changed: {exc}"
                        ) from exc
                    raise

            last_good = self.build_last_good(
                pair,
                builder_family,
                reviewer_family,
                builder_model,
                reviewer_model,
                opencode_version,
                ollama_version,
            )
            lock_payload = self.build_lock(
                project_slug,
                prompt_id,
                pair,
                builder_family,
                reviewer_family,
                builder_source,
                reviewer_source,
                resolution_source,
                opencode_version,
                ollama_version,
                catalog_models,
                builder_model,
                reviewer_model,
            )
            self.persist_cache_transaction(
                self.tested_model_updates(cache_before, cache),
                last_good,
            )
            self.persist_prompt_lock(lock_path, lock_payload)
            return pair, lock_payload


def relative_path(value: str, label: str) -> Path:
    path = Path(value)
    if path.is_absolute() or ".." in path.parts:
        raise ResolutionError(f"{label} must be a safe relative path")
    return path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    def add_lock_location(command: argparse.ArgumentParser) -> None:
        command.add_argument("--session-dir", required=True)
        command.add_argument("--state-root", default="agent-sessions")
        command.add_argument("--prompt-id", required=True)

    resolve = subparsers.add_parser("resolve", help="Resolve and pin a prompt model pair")
    add_lock_location(resolve)
    resolve.add_argument("--project-slug")
    resolve.add_argument("--builder-family", default=DEFAULT_BUILDER_FAMILY)
    resolve.add_argument("--reviewer-family", default=DEFAULT_REVIEWER_FAMILY)
    resolve.add_argument("--builder-model")
    resolve.add_argument("--reviewer-model")
    resolve.add_argument("--refresh-models", action="store_true")

    get = subparsers.add_parser("get", help="Print one exact model ID from a prompt lock")
    add_lock_location(get)
    get.add_argument("--role", required=True, choices=("builder", "reviewer"))

    status = subparsers.add_parser("status", help="Print the prompt lock as compact JSON")
    add_lock_location(status)

    runtime = subparsers.add_parser(
        "runtime-config", help="Print model-only OpenCode inline configuration"
    )
    runtime.add_argument("--builder-model", required=True)
    runtime.add_argument("--reviewer-model", required=True)

    subparsers.add_parser("self-check", help="Check strict catalog parser behavior")
    return parser


def validated_lock_location(args: argparse.Namespace) -> tuple[Path, Path, Path]:
    state_root = relative_path(args.state_root, "state root")
    session_dir = relative_path(args.session_dir, "session directory")
    try:
        session_dir.relative_to(state_root)
    except ValueError as exc:
        raise ResolutionError("Session directory must be inside the model state root") from exc
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", args.prompt_id):
        raise ResolutionError("Prompt ID contains unsupported characters")
    return state_root, session_dir, session_dir / f"{args.prompt_id.upper()}_MODELS.json"


def pair_from_document(lock: dict[str, Any]) -> ModelPair:
    if lock.get("schema_version") == 1:
        builder = lock.get("builder_model")
        reviewer = lock.get("reviewer_model")
    elif lock.get("schema_version") == PROMPT_LOCK_SCHEMA_VERSION:
        builder_record = lock.get("builder")
        reviewer_record = lock.get("reviewer")
        if not isinstance(builder_record, dict) or not isinstance(reviewer_record, dict):
            raise ResolutionError("Prompt model lock is incomplete")
        builder = builder_record.get("exact_id")
        reviewer = reviewer_record.get("exact_id")
    else:
        raise ResolutionError("Unsupported prompt model lock schema")
    return ModelPair(
        validate_model_id(str(builder or ""), "locked builder"),
        validate_model_id(str(reviewer or ""), "locked reviewer"),
    )


def main() -> int:
    args = build_parser().parse_args()
    try:
        if args.command == "self-check":
            sample = "\x1b[92mModels refreshed\x1b[0m\nollama/glm-5.2:cloud\n" \
                "ollama/glm-5.10:cloud\nollama/glm-9:cloud;unsafe"
            if select_latest(sample, "glm-") != "ollama/glm-5.10:cloud":
                raise ResolutionError("strict catalog parser self-check failed")
            print("parser ok")
            return 0

        if args.command == "runtime-config":
            pair = ModelPair(
                validate_model_id(args.builder_model, "builder"),
                validate_model_id(args.reviewer_model, "reviewer"),
            )
            print(runtime_config(pair))
            return 0

        state_root, session_dir, lock_path = validated_lock_location(args)
        if args.command in {"get", "status"}:
            lock = load_json(lock_path, "prompt model lock")
            if lock is None:
                raise ResolutionError(f"Prompt model lock not found: {lock_path}")
            if args.command == "status":
                print(json.dumps(lock, separators=(",", ":"), sort_keys=True))
            else:
                pair = pair_from_document(lock)
                print(pair.builder if args.role == "builder" else pair.reviewer)
            return 0

        project_slug = args.project_slug or session_dir.parent.name
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", project_slug):
            raise ResolutionError("Project slug contains unsupported characters")

        resolver = Resolver(
            workspace=Path("."),
            state_root=state_root,
            opencode_bin=os.environ.get("OPENCODE_BIN", "opencode"),
            ollama_bin=os.environ.get("OLLAMA_BIN", "ollama"),
        )
        pair, _ = resolver.resolve(
            session_dir=session_dir,
            project_slug=project_slug,
            prompt_id=args.prompt_id,
            builder_family=args.builder_family,
            reviewer_family=args.reviewer_family,
            builder_model=args.builder_model,
            reviewer_model=args.reviewer_model,
            refresh_models=args.refresh_models,
        )
    except ResolutionError as exc:
        print(f"model resolution failed: {exc}", file=sys.stderr)
        return 1

    print(
        json.dumps(
            {"builder": pair.builder, "reviewer": pair.reviewer},
            separators=(",", ":"),
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
