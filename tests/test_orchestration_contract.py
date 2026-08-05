from __future__ import annotations

import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


class OrchestrationContractTests(unittest.TestCase):
    def test_meta_agent_uses_standalone_specialist_dispatch(self) -> None:
        instructions = (REPO_ROOT / "codex-config.toml").read_text(
            encoding="utf-8"
        )
        self.assertIn('fork_turns="none"', instructions)
        self.assertIn("non-empty agent id", instructions)
        self.assertIn("accepts only a timeout", instructions)
        self.assertIn("NEVER pass an id to `wait_agent`", instructions)
        self.assertIn(
            "NEVER call `wait_agent` without a successful spawn",
            instructions,
        )

    def test_algorithm_and_experiment_are_leaf_safe(self) -> None:
        for relative in ("agents/algorithm.toml", "agents/experiment.toml"):
            with self.subTest(agent=relative):
                instructions = (REPO_ROOT / relative).read_text(encoding="utf-8")
                self.assertIn("This is a leaf specialist", instructions)
                self.assertIn('fork_turns="none"', instructions)
                self.assertIn("waits with\n`timeout_ms` only", instructions)
                self.assertIn("A failed spawn has no wait", instructions)


if __name__ == "__main__":
    unittest.main()
