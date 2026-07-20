from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from model_resolver import Resolver  # noqa: E402


@unittest.skipUnless(
    os.environ.get("RUN_LIVE_MODEL_TESTS") == "1",
    "set RUN_LIVE_MODEL_TESTS=1 to spend cloud quota on live compatibility checks",
)
class LiveModelResolverTests(unittest.TestCase):
    def test_discovered_cloud_pair_passes_both_smokes_and_locks(self) -> None:
        repository = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as directory:
            state_root = Path(directory) / "agent-sessions"
            session_dir = state_root / "live" / "prompt01"
            resolver = Resolver(workspace=repository, state_root=state_root)
            pair, lock = resolver.resolve(
                session_dir=session_dir,
                project_slug="live",
                prompt_id="prompt01",
                builder_family="minimax-m",
                reviewer_family="glm-",
                builder_model=None,
                reviewer_model=None,
                refresh_models=False,
            )
            self.assertRegex(pair.builder, r"^ollama/minimax-m[0-9]+(?:\.[0-9]+)*:cloud$")
            self.assertRegex(pair.reviewer, r"^ollama/glm-[0-9]+(?:\.[0-9]+)*:cloud$")
            for role in ("builder", "reviewer"):
                self.assertTrue(lock[role]["manifest_ready"])
                self.assertEqual(lock[role]["runtime_status"], "passed")
                self.assertEqual(lock[role]["inference_smoke"], "passed")
                self.assertEqual(lock[role]["tool_smoke"], "passed")
            self.assertTrue((session_dir / "PROMPT01_MODELS.json").is_file())
            self.assertFalse(any(state_root.rglob("*.raw.log")))


if __name__ == "__main__":
    unittest.main()
