from __future__ import annotations

import json
import os
import shutil
import stat
import subprocess
import tempfile
import textwrap
import unittest
from pathlib import Path


REPOSITORY = Path(__file__).resolve().parents[1]


class AttachedLauncherTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.workspace = Path(self.temporary.name)
        (self.workspace / "scripts").mkdir()
        (self.workspace / "agent-sessions/sample/prompt01").mkdir(parents=True)
        (self.workspace / "fake-bin").mkdir()
        for name in ("model_resolver.py", "model_runtime.zsh", "run_reviewer.zsh"):
            shutil.copy2(REPOSITORY / "scripts" / name, self.workspace / "scripts" / name)
        (self.workspace / "AGENTS.md").write_text("# Fake agent rules\n", encoding="utf-8")
        (self.workspace / "opencode.json").write_text(
            json.dumps(
                {
                    "model": "ollama/minimax-m3:cloud",
                    "small_model": "ollama/glm-5.1:cloud",
                    "agent": {"glm-reviewer": {"model": "ollama/glm-5.1:cloud"}},
                }
            ),
            encoding="utf-8",
        )
        session = self.workspace / "agent-sessions/sample/prompt01"
        (session / "PROMPT_REVIEWER.md").write_text("Review the fake change.\n", encoding="utf-8")
        (session / "PROMPT01_MODELS.json").write_text(
            json.dumps(
                {
                    "schema_version": 2,
                    "resolver_version": "2.1",
                    "project_slug": "sample",
                    "prompt_id": "prompt01",
                    "resolved_at": "2026-01-01T00:00:00+00:00",
                    "resolution_source": "refreshed_catalog",
                    "provider": "ollama",
                    "toolchain": {
                        "opencode": "9.9.0",
                        "ollama": "ollama version 8.8.0",
                    },
                    "override_context": {"builder": None, "reviewer": None},
                    "builder": {
                        "family": "minimax-m",
                        "exact_id": "ollama/minimax-m3:cloud",
                        "manifest_id": "minimax-m3:cloud",
                        "source": "family",
                        "catalog_visible": True,
                        "manifest_ready": True,
                        "runtime_status": "passed",
                        "inference_smoke": "passed",
                        "tool_smoke": "passed",
                    },
                    "reviewer": {
                        "family": "glm-",
                        "exact_id": "ollama/glm-5.2:cloud",
                        "manifest_id": "glm-5.2:cloud",
                        "source": "family",
                        "catalog_visible": True,
                        "manifest_ready": True,
                        "runtime_status": "passed",
                        "inference_smoke": "passed",
                        "tool_smoke": "passed",
                    },
                }
            ),
            encoding="utf-8",
        )
        self.invocation_log = self.workspace / "invocation.json"
        self.opencode_bin = self.workspace / "fake-bin/opencode"
        self.ollama_bin = self.workspace / "fake-bin/ollama"
        self._write_executable(
            self.opencode_bin,
            """
            #!/usr/bin/env python3
            import json
            import os
            import sys
            from pathlib import Path

            args = sys.argv[1:]
            if args == ["--version"]:
                print("9.9.0")
                raise SystemExit(0)
            if args and args[0] == "run":
                payload = {
                    "args": args,
                    "inline": json.loads(os.environ.get("OPENCODE_CONFIG_CONTENT", "{}")),
                }
                Path(os.environ["FAKE_INVOCATION_LOG"]).write_text(
                    json.dumps(payload), encoding="utf-8"
                )
                print("WORKFLOW_OK")
                raise SystemExit(0)
            raise SystemExit(2)
            """,
        )
        self._write_executable(
            self.ollama_bin,
            """
            #!/usr/bin/env python3
            import sys

            args = sys.argv[1:]
            if args == ["--version"]:
                print("ollama version 8.8.0")
                raise SystemExit(0)
            if args and args[0] == "show":
                raise SystemExit(0)
            raise SystemExit(2)
            """,
        )

    @staticmethod
    def _write_executable(path: Path, body: str) -> None:
        path.write_text(textwrap.dedent(body).lstrip(), encoding="utf-8")
        path.chmod(path.stat().st_mode | stat.S_IXUSR)

    def test_attached_reviewer_uses_locked_model_not_bootstrap(self) -> None:
        bootstrap = json.loads((self.workspace / "opencode.json").read_text(encoding="utf-8"))
        self.assertEqual(bootstrap["agent"]["glm-reviewer"]["model"], "ollama/glm-5.1:cloud")
        environment = os.environ.copy()
        environment.update(
            {
                "PATH": f"{self.opencode_bin.parent}:{environment['PATH']}",
                "OPENCODE_BIN": str(self.opencode_bin),
                "OLLAMA_BIN": str(self.ollama_bin),
                "FAKE_INVOCATION_LOG": str(self.invocation_log),
            }
        )
        completed = subprocess.run(
            [
                "zsh",
                "scripts/run_reviewer.zsh",
                "sample",
                "prompt01",
                "--attach",
                "http://localhost:4096",
            ],
            cwd=self.workspace,
            env=environment,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        invocation = json.loads(self.invocation_log.read_text(encoding="utf-8"))
        args = invocation["args"]
        self.assertEqual(args[args.index("--model") + 1], "ollama/glm-5.2:cloud")
        self.assertEqual(args[args.index("--attach") + 1], "http://localhost:4096")
        self.assertNotIn("small_model", invocation["inline"])


class CombinedRunnerTests(unittest.TestCase):
    def test_refresh_is_resolved_once_by_builder_then_reviewer_consumes_lock(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            scripts = workspace / "scripts"
            scripts.mkdir()
            shutil.copy2(
                REPOSITORY / "scripts/run_prompt_agents.zsh",
                scripts / "run_prompt_agents.zsh",
            )
            log = workspace / "calls.log"
            for role in ("builder", "reviewer"):
                (scripts / f"run_{role}.zsh").write_text(
                    f'#!/usr/bin/env zsh\nprint -r -- "{role}:$*" >> "$FAKE_CALL_LOG"\n',
                    encoding="utf-8",
                )
            environment = os.environ.copy()
            environment["FAKE_CALL_LOG"] = str(log)
            completed = subprocess.run(
                [
                    "zsh",
                    "scripts/run_prompt_agents.zsh",
                    "sample",
                    "prompt01",
                    "--attach",
                    "http://localhost:4096",
                    "--refresh-models",
                ],
                cwd=workspace,
                env=environment,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            calls = log.read_text(encoding="utf-8").splitlines()
            self.assertIn("--refresh-models", calls[0])
            self.assertIn("--attach http://localhost:4096", calls[0])
            self.assertNotIn("--refresh-models", calls[1])
            self.assertIn("--attach http://localhost:4096", calls[1])
