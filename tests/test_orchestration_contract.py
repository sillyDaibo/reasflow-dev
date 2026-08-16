from __future__ import annotations

import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


class OrchestrationContractTests(unittest.TestCase):
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
