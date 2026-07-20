from __future__ import annotations

import json
import os
import stat
import subprocess
import sys
import tempfile
import textwrap
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import model_resolver  # noqa: E402
from model_resolver import (  # noqa: E402
    ModelPair,
    ResolutionError,
    Resolver,
    VerificationError,
    atomic_write_json,
    family_candidates,
    runtime_config,
    select_latest,
    strip_ansi,
    validate_model_id,
)


BASE_CATALOG = """
\x1b[92mModels cache refreshed\x1b[0m

warning: synthetic fixture
ollama/glm-5:cloud
ollama/glm-5.1:cloud
ollama/glm-5.2:cloud
ollama/glm-5.2:cloud
ollama/minimax-m3:cloud
"""


class CatalogTests(unittest.TestCase):
    def test_smoke_agents_have_only_the_intended_permissions(self) -> None:
        root = Path(__file__).resolve().parents[1]
        config = json.loads((root / "opencode.json").read_text(encoding="utf-8"))
        self.assertEqual(config["autoupdate"], "notify")
        self.assertEqual(config["small_model"], "ollama/glm-5.2:cloud")
        self.assertEqual(config["mcp"], {})
        self.assertEqual(
            config["agent"]["model-inference-smoke"]["permission"], {"*": "deny"}
        )
        self.assertEqual(
            config["agent"]["model-tool-smoke"]["permission"],
            {
                "*": "deny",
                "read": {
                    "*": "deny",
                    ".opencode/model-smoke/FIXTURE.txt": "allow",
                },
            },
        )

    def test_numeric_versions_are_sorted_numerically(self) -> None:
        catalog = "\n".join(
            (
                "ollama/glm-5.2:cloud",
                "ollama/glm-5.10:cloud",
                "ollama/glm-6:7b",
                "ollama/glm-7-beta:cloud",
                "ollama/glm-8-rc1:cloud",
                "ollama/glm-9-latest:cloud",
                "ollama/glm-10-flash:cloud",
                "ollama/glm-11-instruct:cloud",
                "other/glm-99:cloud",
                "ollama/not-glm-99:cloud",
            )
        )
        self.assertEqual(select_latest(catalog, "glm-"), "ollama/glm-5.10:cloud")

    def test_numeric_tuple_edge_is_explicit(self) -> None:
        catalog = "ollama/glm-5.2:cloud\nollama/glm-5.2.0:cloud"
        self.assertEqual(select_latest(catalog, "glm-"), "ollama/glm-5.2.0:cloud")

    def test_ansi_headers_blanks_and_duplicates_are_ignored(self) -> None:
        self.assertEqual(
            family_candidates(BASE_CATALOG, "minimax-m"),
            [((3,), "ollama/minimax-m3:cloud")],
        )
        self.assertNotIn("\x1b", strip_ansi(BASE_CATALOG))

    def test_malformed_and_shell_looking_catalog_text_is_untrusted(self) -> None:
        catalog = "\n".join(
            (
                "ollama/glm-5.2:cloud; touch unsafe",
                "$(ollama/glm-99:cloud)",
                "ollama/glm-6:cloud extra",
                "ollama/glm-5.2:cloud",
            )
        )
        self.assertEqual(select_latest(catalog, "glm-"), "ollama/glm-5.2:cloud")

    def test_invalid_family_and_empty_catalog_fail(self) -> None:
        with self.assertRaises(ResolutionError):
            select_latest(BASE_CATALOG, "glm-.*")
        with self.assertRaises(ResolutionError):
            select_latest("not a catalog", "glm-")

    def test_exact_override_is_strict_cloud_only(self) -> None:
        self.assertEqual(
            validate_model_id("ollama/custom-builder:cloud", "builder"),
            "ollama/custom-builder:cloud",
        )
        for invalid in (
            "ollama/custom-builder:7b",
            "other/custom-builder:cloud",
            "ollama/custom-builder:cloud;unsafe",
        ):
            with self.subTest(invalid=invalid), self.assertRaises(ResolutionError):
                validate_model_id(invalid, "builder")

    def test_runtime_config_does_not_couple_small_model(self) -> None:
        pair = ModelPair("ollama/minimax-m3:cloud", "ollama/glm-5.2:cloud")
        config = json.loads(runtime_config(pair))
        self.assertEqual(config["model"], pair.builder)
        self.assertEqual(config["agent"]["glm-reviewer"]["model"], pair.reviewer)
        self.assertNotIn("small_model", config)

    def test_structured_smoke_sentinel_rejects_extra_or_malformed_stdout(self) -> None:
        sentinel_event = json.dumps(
            {
                "type": "text",
                "part": {"type": "text", "text": "OPENCODE_MODEL_SMOKE_OK"},
            }
        )
        extra_event = json.dumps(
            {"type": "text", "part": {"type": "text", "text": "extra prose"}}
        )
        self.assertTrue(
            Resolver.exact_structured_response(sentinel_event, "OPENCODE_MODEL_SMOKE_OK")
        )
        self.assertFalse(
            Resolver.exact_structured_response(
                f"{extra_event}\n{sentinel_event}\n", "OPENCODE_MODEL_SMOKE_OK"
            )
        )
        self.assertFalse(
            Resolver.exact_structured_response(
                "OPENCODE_MODEL_SMOKE_OK\n", "OPENCODE_MODEL_SMOKE_OK"
            )
        )

    def test_atomic_json_write_preserves_old_file_when_replace_fails(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "selection.json"
            target.write_text('{"old":true}\n', encoding="utf-8")
            before = target.read_bytes()
            with mock.patch.object(model_resolver.os, "replace", side_effect=OSError("interrupted")):
                with self.assertRaises(OSError):
                    atomic_write_json(target, {"new": True})
            self.assertEqual(target.read_bytes(), before)
            self.assertEqual(list(target.parent.glob("*.tmp")), [])


class ResolverLifecycleTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.workspace = Path(self.temporary.name)
        self.bin_dir = self.workspace / "fake-bin"
        self.bin_dir.mkdir()
        self.ollama_state = self.workspace / "ollama-state"
        self.ollama_state.mkdir()
        self.opencodelog = self.workspace / "opencode-runs.jsonl"
        self.cataloglog = self.workspace / "catalog-runs.log"
        self.opencode_bin = self.bin_dir / "opencode"
        self.ollama_bin = self.bin_dir / "ollama"
        self._write_executable(
            self.opencode_bin,
            """
            #!/usr/bin/env python3
            import json
            import os
            import sys
            import time
            from pathlib import Path

            args = sys.argv[1:]
            if args == ["--version"]:
                print(os.environ.get("FAKE_OPENCODE_VERSION", "9.9.0"))
                raise SystemExit(0)
            if args[:3] == ["models", "ollama", "--refresh"]:
                log = os.environ.get("FAKE_CATALOG_LOG")
                if log:
                    with Path(log).open("a", encoding="utf-8") as handle:
                        handle.write("refresh\\n")
                if os.environ.get("FAKE_CATALOG_FAIL") == "1":
                    print("catalog unavailable", file=sys.stderr)
                    raise SystemExit(1)
                print(os.environ.get("FAKE_CATALOG", ""))
                raise SystemExit(0)
            if args[:2] == ["debug", "config"]:
                config = json.loads(os.environ.get("OPENCODE_CONFIG_CONTENT", "{}"))
                blocked_role = os.environ.get("FAKE_MANAGED_OVERRIDE")
                if blocked_role:
                    config.setdefault("agent", {}).setdefault(blocked_role, {})["model"] = (
                        "ollama/managed-override:cloud"
                    )
                print(json.dumps(config))
                raise SystemExit(0)
            if args[:2] == ["debug", "agent"]:
                agent = args[2]
                config = json.loads(os.environ.get("OPENCODE_CONFIG_CONTENT", "{}"))
                model = config.get("agent", {}).get(agent, {}).get("model", config.get("model"))
                if os.environ.get("FAKE_MANAGED_OVERRIDE") == agent:
                    model = "ollama/managed-override:cloud"
                provider, model_id = model.split("/", 1)
                print(
                    json.dumps(
                        {"name": agent, "model": {"providerID": provider, "modelID": model_id}}
                    )
                )
                raise SystemExit(0)
            if args and args[0] == "run":
                model = args[args.index("--model") + 1]
                agent = args[args.index("--agent") + 1]
                attach = args[args.index("--attach") + 1] if "--attach" in args else None
                output_format = args[args.index("--format") + 1] if "--format" in args else None
                log = os.environ.get("FAKE_OPENCODE_LOG")
                if log:
                    with Path(log).open("a", encoding="utf-8") as handle:
                        handle.write(
                            json.dumps(
                                {
                                    "model": model,
                                    "agent": agent,
                                    "attach": attach,
                                    "format": output_format,
                                }
                            )
                            + "\\n"
                        )
                delay = float(os.environ.get("FAKE_SMOKE_DELAY", "0"))
                if delay and agent.startswith("model-"):
                    time.sleep(delay)
                if agent == "model-inference-smoke":
                    if os.environ.get("FAKE_INFERENCE_FAIL") == model:
                        print("wrong inference response")
                        raise SystemExit(0)
                    print(
                        json.dumps(
                            {
                                "type": "text",
                                "part": {"type": "text", "text": "OPENCODE_MODEL_SMOKE_OK"},
                            }
                        )
                    )
                    raise SystemExit(0)
                if agent == "model-tool-smoke":
                    if os.environ.get("FAKE_TOOL_FAIL") == model:
                        print("wrong tool response")
                        raise SystemExit(0)
                    if os.environ.get("FAKE_SKIP_TOOL") != model:
                        print(
                            json.dumps(
                                {
                                    "type": "tool_use",
                                    "part": {
                                        "type": "tool",
                                        "tool": "read",
                                        "state": {
                                            "status": "completed",
                                            "input": {
                                                "filePath": ".opencode/model-smoke/FIXTURE.txt"
                                            },
                                            "output": "7F3A",
                                        },
                                    },
                                }
                            )
                        )
                    print(
                        json.dumps(
                            {
                                "type": "text",
                                "part": {
                                    "type": "text",
                                    "text": "OPENCODE_TOOL_SMOKE_OK:7F3A",
                                },
                            }
                        )
                    )
                    raise SystemExit(0)
                print("WORKFLOW_OK")
                raise SystemExit(0)
            print("unsupported fake OpenCode command", file=sys.stderr)
            raise SystemExit(2)
            """,
        )
        self._write_executable(
            self.ollama_bin,
            """
            #!/usr/bin/env python3
            import os
            import sys
            from pathlib import Path

            args = sys.argv[1:]
            if args == ["--version"]:
                print(os.environ.get("FAKE_OLLAMA_VERSION", "ollama version 8.8.0"))
                raise SystemExit(0)
            state = Path(os.environ["FAKE_OLLAMA_STATE"])
            model = args[1] if len(args) > 1 else ""
            marker = state / model.replace("/", "_").replace(":", "_")
            if args and args[0] == "show":
                if os.environ.get("FAKE_UNAVAILABLE") == model:
                    raise SystemExit(1)
                raise SystemExit(0 if marker.exists() else 1)
            if args and args[0] == "pull":
                if os.environ.get("FAKE_PULL_FAIL") == model:
                    raise SystemExit(1)
                marker.touch()
                print("pulled")
                raise SystemExit(0)
            raise SystemExit(2)
            """,
        )
        self.environment = {
            "FAKE_CATALOG": BASE_CATALOG,
            "FAKE_OLLAMA_STATE": str(self.ollama_state),
            "FAKE_OPENCODE_LOG": str(self.opencodelog),
            "FAKE_CATALOG_LOG": str(self.cataloglog),
            "FAKE_OPENCODE_VERSION": "9.9.0",
            "FAKE_OLLAMA_VERSION": "ollama version 8.8.0",
        }
        self.resolver = self._new_resolver()

    def _new_resolver(self) -> Resolver:
        return Resolver(
            workspace=self.workspace,
            state_root=Path("agent-sessions"),
            opencode_bin=str(self.opencode_bin),
            ollama_bin=str(self.ollama_bin),
        )

    @staticmethod
    def _write_executable(path: Path, body: str) -> None:
        path.write_text(textwrap.dedent(body).lstrip(), encoding="utf-8")
        path.chmod(path.stat().st_mode | stat.S_IXUSR)

    def _resolve(
        self,
        prompt: str = "prompt01",
        refresh: bool = False,
        builder_model: str | None = None,
        reviewer_model: str | None = None,
        resolver: Resolver | None = None,
    ) -> tuple[ModelPair, dict[str, object]]:
        with mock.patch.dict(os.environ, self.environment, clear=False):
            return (resolver or self.resolver).resolve(
                session_dir=Path("agent-sessions") / "sample" / prompt,
                project_slug="sample",
                prompt_id=prompt,
                builder_family="minimax-m",
                reviewer_family="glm-",
                builder_model=builder_model,
                reviewer_model=reviewer_model,
                refresh_models=refresh,
            )

    def _run_records(self) -> list[dict[str, object]]:
        if not self.opencodelog.exists():
            return []
        return [json.loads(line) for line in self.opencodelog.read_text(encoding="utf-8").splitlines()]

    def _lock_path(self, prompt: str = "prompt01") -> Path:
        return self.workspace / f"agent-sessions/sample/{prompt}/{prompt.upper()}_MODELS.json"

    def test_first_run_pulls_two_stage_smokes_and_locks_pair(self) -> None:
        pair, lock = self._resolve()
        self.assertEqual(pair, ModelPair("ollama/minimax-m3:cloud", "ollama/glm-5.2:cloud"))
        self.assertEqual(lock["schema_version"], 2)
        self.assertEqual(lock["project_slug"], "sample")
        self.assertEqual(lock["resolution_source"], "refreshed_catalog")
        self.assertEqual(lock["builder"]["manifest_id"], "minimax-m3:cloud")
        self.assertEqual(lock["builder"]["runtime_status"], "passed")
        self.assertEqual(lock["reviewer"]["tool_smoke"], "passed")
        self.assertTrue(lock["reviewer"]["catalog_visible"])
        self.assertTrue((self.ollama_state / "minimax-m3_cloud").is_file())
        self.assertTrue((self.ollama_state / "glm-5.2_cloud").is_file())
        agents = [record["agent"] for record in self._run_records()]
        self.assertTrue(all(record["format"] == "json" for record in self._run_records()))
        self.assertEqual(
            agents,
            [
                "model-inference-smoke",
                "model-tool-smoke",
                "model-inference-smoke",
                "model-tool-smoke",
            ],
        )
        self.assertTrue(self._lock_path().is_file())
        cache = json.loads((self.workspace / "agent-sessions/.model-cache.json").read_text())
        self.assertEqual(cache["last_good"]["reviewer"]["tool_smoke"], "passed")
        self.assertEqual(cache["last_good"]["toolchain"]["ollama"], "ollama version 8.8.0")
        persisted = json.dumps({"lock": lock, "cache": cache})
        self.assertNotIn("OPENCODE_MODEL_SMOKE_OK", persisted)
        self.assertNotIn("OPENCODE_TOOL_SMOKE_OK:7F3A", persisted)

    def test_existing_lock_is_reused_without_catalog_or_smoke(self) -> None:
        expected, _ = self._resolve()
        self.environment["FAKE_CATALOG_FAIL"] = "1"
        before_records = self._run_records()
        before_catalog = self.cataloglog.read_text(encoding="utf-8")
        actual, _ = self._resolve()
        self.assertEqual(actual, expected)
        self.assertEqual(self._run_records(), before_records)
        self.assertEqual(self.cataloglog.read_text(encoding="utf-8"), before_catalog)

    def test_builder_override_with_reviewer_family_resolution(self) -> None:
        pair, lock = self._resolve(builder_model="ollama/custom-builder:cloud")
        self.assertEqual(pair.builder, "ollama/custom-builder:cloud")
        self.assertEqual(pair.reviewer, "ollama/glm-5.2:cloud")
        self.assertEqual(lock["builder"]["source"], "exact_override")
        self.assertEqual(lock["reviewer"]["source"], "family")

    def test_reviewer_override_with_builder_family_resolution(self) -> None:
        pair, lock = self._resolve(reviewer_model="ollama/custom-reviewer:cloud")
        self.assertEqual(pair.builder, "ollama/minimax-m3:cloud")
        self.assertEqual(pair.reviewer, "ollama/custom-reviewer:cloud")
        self.assertEqual(lock["reviewer"]["source"], "exact_override")

    def test_invalid_override_fails_before_catalog(self) -> None:
        with self.assertRaisesRegex(ResolutionError, "strict Ollama Cloud ID"):
            self._resolve(builder_model="ollama/custom-builder:7b")
        self.assertFalse(self.cataloglog.exists())

    def test_conflicting_override_requires_refresh(self) -> None:
        self._resolve()
        with self.assertRaisesRegex(ResolutionError, "conflicts with the prompt lock"):
            self._resolve(reviewer_model="ollama/glm-5.1:cloud")

    def test_explicit_override_failure_never_uses_lkg(self) -> None:
        self._resolve(
            builder_model="ollama/custom-builder:cloud",
            reviewer_model="ollama/custom-reviewer:cloud",
        )
        self.environment["FAKE_UNAVAILABLE"] = "custom-builder:cloud"
        self.environment["FAKE_PULL_FAIL"] = "custom-builder:cloud"
        with self.assertRaises(VerificationError):
            self._resolve(
                prompt="prompt02",
                builder_model="ollama/custom-builder:cloud",
                reviewer_model="ollama/custom-reviewer:cloud",
            )
        self.assertFalse(self._lock_path("prompt02").exists())

    def test_successful_refresh_replaces_lock_after_pair_verification(self) -> None:
        self._resolve()
        before = self._lock_path().read_bytes()
        self.environment["FAKE_CATALOG"] = BASE_CATALOG + "\nollama/glm-5.10:cloud\n"
        pair, lock = self._resolve(refresh=True)
        self.assertEqual(pair.reviewer, "ollama/glm-5.10:cloud")
        self.assertNotEqual(self._lock_path().read_bytes(), before)
        self.assertEqual(lock["reviewer"]["tool_smoke"], "passed")

    def test_failed_refresh_preserves_lock_byte_for_byte(self) -> None:
        self._resolve()
        before = self._lock_path().read_bytes()
        self.environment["FAKE_CATALOG"] = "ollama/minimax-m4:cloud\nollama/glm-6:cloud"
        self.environment["FAKE_TOOL_FAIL"] = "ollama/glm-6:cloud"
        with self.assertRaisesRegex(ResolutionError, "existing prompt lock was not changed"):
            self._resolve(refresh=True)
        self.assertEqual(self._lock_path().read_bytes(), before)

    def test_catalog_refresh_failure_preserves_existing_lock(self) -> None:
        self._resolve()
        before = self._lock_path().read_bytes()
        self.environment["FAKE_CATALOG_FAIL"] = "1"
        with self.assertRaisesRegex(ResolutionError, "existing prompt lock was not changed"):
            self._resolve(refresh=True)
        self.assertEqual(self._lock_path().read_bytes(), before)

    def test_catalog_outage_uses_compatible_lkg_for_new_prompt(self) -> None:
        expected, _ = self._resolve()
        self.environment["FAKE_CATALOG_FAIL"] = "1"
        pair, lock = self._resolve(prompt="prompt02")
        self.assertEqual(pair, expected)
        self.assertEqual(lock["resolution_source"], "last_known_good")
        self.assertEqual(lock["builder"]["catalog_visible"], None)

    def test_catalog_outage_without_lkg_fails_before_lock(self) -> None:
        self.environment["FAKE_CATALOG_FAIL"] = "1"
        with self.assertRaisesRegex(ResolutionError, "no matching last-known-good"):
            self._resolve()
        self.assertFalse(self._lock_path().exists())

    def test_inference_smoke_failure_is_not_eligible_for_fallback(self) -> None:
        self.environment["FAKE_INFERENCE_FAIL"] = "ollama/glm-5.2:cloud"
        with self.assertRaises(VerificationError):
            self._resolve()
        self.assertFalse(self._lock_path().exists())
        self.assertFalse((self.workspace / "agent-sessions/.model-cache.json").exists())

    def test_tool_smoke_failure_is_not_eligible_for_fallback(self) -> None:
        self.environment["FAKE_TOOL_FAIL"] = "ollama/glm-5.2:cloud"
        with self.assertRaises(VerificationError):
            self._resolve()
        self.assertFalse(self._lock_path().exists())

    def test_tool_sentinel_without_completed_read_is_rejected(self) -> None:
        self.environment["FAKE_SKIP_TOOL"] = "ollama/glm-5.2:cloud"
        with self.assertRaises(VerificationError):
            self._resolve()
        self.assertFalse(self._lock_path().exists())

    def test_new_candidate_verification_failure_does_not_use_existing_lkg(self) -> None:
        self._resolve()
        self.environment["FAKE_CATALOG"] = (
            BASE_CATALOG + "\nollama/minimax-m4:cloud\nollama/glm-6:cloud\n"
        )
        self.environment["FAKE_TOOL_FAIL"] = "ollama/glm-6:cloud"
        with self.assertRaises(VerificationError):
            self._resolve(prompt="prompt02")
        self.assertFalse(self._lock_path("prompt02").exists())

    def test_managed_config_model_mismatch_fails_clearly(self) -> None:
        self.environment["FAKE_MANAGED_OVERRIDE"] = "glm-reviewer"
        with self.assertRaisesRegex(VerificationError, "managed or higher-priority"):
            self._resolve()
        self.assertFalse(self._lock_path().exists())

    def test_locked_model_catalog_absence_does_not_invalidate_runtime(self) -> None:
        expected, _ = self._resolve()
        self.environment["FAKE_CATALOG_FAIL"] = "1"
        pair, _ = self._resolve()
        self.assertEqual(pair, expected)

    def test_genuinely_unavailable_locked_model_fails(self) -> None:
        pair, _ = self._resolve()
        tag = pair.reviewer.removeprefix("ollama/")
        marker = self.ollama_state / tag.replace("/", "_").replace(":", "_")
        marker.unlink()
        self.environment["FAKE_UNAVAILABLE"] = tag
        self.environment["FAKE_PULL_FAIL"] = tag
        with self.assertRaises(VerificationError):
            self._resolve()

    def test_corrupt_lock_fails_but_explicit_refresh_can_replace_it(self) -> None:
        self._resolve()
        self._lock_path().write_text("not-json", encoding="utf-8")
        with self.assertRaises(ResolutionError):
            self._resolve()
        pair, lock = self._resolve(refresh=True)
        self.assertEqual(pair.reviewer, "ollama/glm-5.2:cloud")
        self.assertEqual(lock["schema_version"], 2)

    def test_incomplete_lock_fails_with_refresh_guidance(self) -> None:
        self._resolve()
        lock = json.loads(self._lock_path().read_text(encoding="utf-8"))
        del lock["reviewer"]
        self._lock_path().write_text(json.dumps(lock), encoding="utf-8")
        with self.assertRaisesRegex(ResolutionError, "rerun with --refresh-models"):
            self._resolve()

    def test_corrupt_lkg_is_rebuilt_only_after_catalog_verification(self) -> None:
        cache_path = self.workspace / "agent-sessions/.model-cache.json"
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_text("not-json", encoding="utf-8")
        pair, _ = self._resolve()
        self.assertEqual(pair.builder, "ollama/minimax-m3:cloud")
        rebuilt = json.loads(cache_path.read_text(encoding="utf-8"))
        self.assertEqual(rebuilt["schema_version"], 2)

    def test_opencode_version_change_reverifies_same_locked_pair(self) -> None:
        expected, _ = self._resolve()
        count = len(self._run_records())
        self.environment["FAKE_OPENCODE_VERSION"] = "9.10.0"
        pair, lock = self._resolve()
        self.assertEqual(pair, expected)
        self.assertEqual(len(self._run_records()) - count, 4)
        self.assertEqual(lock["toolchain"]["opencode"], "9.10.0")
        self.assertEqual(lock["resolution_source"], "prompt_lock_reverified")

    def test_ollama_version_change_reverifies_same_locked_pair(self) -> None:
        expected, _ = self._resolve()
        count = len(self._run_records())
        self.environment["FAKE_OLLAMA_VERSION"] = "ollama version 8.9.0"
        pair, lock = self._resolve()
        self.assertEqual(pair, expected)
        self.assertEqual(len(self._run_records()) - count, 4)
        self.assertEqual(lock["toolchain"]["ollama"], "ollama version 8.9.0")

    def test_stale_resolver_verification_is_resmoked_during_lkg_fallback(self) -> None:
        expected, _ = self._resolve()
        cache_path = self.workspace / "agent-sessions/.model-cache.json"
        cache = json.loads(cache_path.read_text(encoding="utf-8"))
        for record in cache["tested_models"].values():
            record["resolver_version"] = "old-verification-policy"
        cache_path.write_text(json.dumps(cache), encoding="utf-8")
        count = len(self._run_records())
        self.environment["FAKE_CATALOG_FAIL"] = "1"
        pair, lock = self._resolve(prompt="prompt02")
        self.assertEqual(pair, expected)
        self.assertEqual(lock["resolution_source"], "last_known_good")
        self.assertEqual(len(self._run_records()) - count, 4)

    def test_concurrent_first_runs_share_one_verification_transaction(self) -> None:
        self.environment["FAKE_SMOKE_DELAY"] = "0.05"

        def run(resolver: Resolver) -> tuple[ModelPair, dict[str, object]]:
            return resolver.resolve(
                session_dir=Path("agent-sessions/sample/prompt01"),
                project_slug="sample",
                prompt_id="prompt01",
                builder_family="minimax-m",
                reviewer_family="glm-",
                builder_model=None,
                reviewer_model=None,
                refresh_models=False,
            )

        with mock.patch.dict(os.environ, self.environment, clear=False):
            with ThreadPoolExecutor(max_workers=2) as pool:
                first = pool.submit(run, self._new_resolver())
                second = pool.submit(run, self._new_resolver())
                first_pair, _ = first.result(timeout=10)
                second_pair, _ = second.result(timeout=10)
        self.assertEqual(first_pair, second_pair)
        self.assertEqual(len(self.cataloglog.read_text(encoding="utf-8").splitlines()), 1)
        self.assertEqual(len(self._run_records()), 4)

    def test_cli_resolve_get_status_and_self_check_are_machine_readable(self) -> None:
        script = Path(__file__).resolve().parents[1] / "scripts/model_resolver.py"
        environment = os.environ.copy()
        environment.update(self.environment)
        environment["OPENCODE_BIN"] = str(self.opencode_bin)
        environment["OLLAMA_BIN"] = str(self.ollama_bin)
        resolve = subprocess.run(
            [
                sys.executable,
                str(script),
                "resolve",
                "--session-dir",
                "agent-sessions/sample/prompt03",
                "--project-slug",
                "sample",
                "--prompt-id",
                "prompt03",
            ],
            cwd=self.workspace,
            env=environment,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        self.assertEqual(resolve.returncode, 0, resolve.stderr)
        self.assertEqual(
            json.loads(resolve.stdout),
            {
                "builder": "ollama/minimax-m3:cloud",
                "reviewer": "ollama/glm-5.2:cloud",
            },
        )

        get = subprocess.run(
            [
                sys.executable,
                str(script),
                "get",
                "--session-dir",
                "agent-sessions/sample/prompt03",
                "--prompt-id",
                "prompt03",
                "--role",
                "reviewer",
            ],
            cwd=self.workspace,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        self.assertEqual(get.stdout, "ollama/glm-5.2:cloud\n")
        self.assertEqual(get.stderr, "")

        status = subprocess.run(
            [
                sys.executable,
                str(script),
                "status",
                "--session-dir",
                "agent-sessions/sample/prompt03",
                "--prompt-id",
                "prompt03",
            ],
            cwd=self.workspace,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        self.assertEqual(json.loads(status.stdout)["schema_version"], 2)

        self_check = subprocess.run(
            [sys.executable, str(script), "self-check"],
            cwd=self.workspace,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        self.assertEqual(self_check.stdout, "parser ok\n")
        self.assertEqual(self_check.stderr, "")


if __name__ == "__main__":
    unittest.main()
