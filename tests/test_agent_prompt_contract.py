from __future__ import annotations

import re
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
PROMPT_MARKER = "developer_instructions = '''"
RULE_MARKERS = re.compile(
    r"\b(if|when|unless|otherwise|must|required|never|always|only|"
    r"do not|forbidden|critical)\b",
    re.IGNORECASE,
)


def prompt_for(relative: str) -> str:
    text = (REPO_ROOT / relative).read_text(encoding="utf-8")
    return text.split(PROMPT_MARKER, 1)[1].rsplit("'''", 1)[0]


def text_for(relative: str) -> str:
    return (REPO_ROOT / relative).read_text(encoding="utf-8")


class AgentPromptContractTests(unittest.TestCase):
    def test_prompts_keep_a_small_high_signal_context(self) -> None:
        budgets = {
            "agents/algorithm.toml": (8000, 180, 30),
            "agents/experiment.toml": (9000, 190, 35),
        }
        for relative, (max_chars, max_lines, max_rule_markers) in budgets.items():
            with self.subTest(agent=relative):
                prompt = prompt_for(relative)
                self.assertLessEqual(len(prompt), max_chars)
                self.assertLessEqual(len(prompt.splitlines()), max_lines)
                self.assertLessEqual(
                    len(RULE_MARKERS.findall(prompt)),
                    max_rule_markers,
                )
                self.assertNotIn("## Scenario", prompt)
                self.assertNotIn("Always do this first", prompt)
                self.assertNotIn("Complete testing workflow", prompt)
                self.assertNotIn("```", prompt)

    def test_algorithm_prompt_preserves_outcome_contracts(self) -> None:
        prompt = prompt_for("agents/algorithm.toml")
        for required in (
            "Alg_Exp/algorithm_plan.md",
            "Alg_Exp/algorithm_test_plan.md",
            "ReaScholar evidence table",
            "copied, adapted, or novel",
            "knowledge-card-retrieval",
            "reascholar-evidence-retrieval",
            "Keep proposed hybrid modules out of that query",
            "inspect the full primary candidate list",
            "at most two knowledge-card searches",
            "algorithm-design-review",
            "evidence-backed anchor",
            "selection semantics",
            "anchor-aligned baseline or rollback",
            "algorithm-prototyping-workflow",
            "toy-verification",
            "commands that actually ran",
        ):
            with self.subTest(required=required):
                self.assertIn(required, prompt)
        self.assertRegex(prompt, r"at most\s+one focused follow-up")

    def test_experiment_prompt_preserves_evidence_and_execution_gates(self) -> None:
        prompt = prompt_for("agents/experiment.toml")
        for required in (
            "Alg_Exp/document/experiment_plan.md",
            "Alg_Exp/document/execution_contract.json",
            "task-relevance gate",
            "accepted and rejected paper keys",
            "knowledge-card-retrieval",
            "reascholar-evidence-retrieval",
            "Inspect the full primary candidate list",
            "at most two knowledge-card searches",
            "--require-ready",
            "experiment-design",
            "Anchor the protocol",
            "ablations rather than replacements",
            "compact evidence-relevance table",
            "experiment-execution",
            "auto-tuning",
            "recomputed from saved artifacts",
        ):
            with self.subTest(required=required):
                self.assertIn(required, prompt)
        self.assertRegex(prompt, r"at most\s+one focused follow-up")

    def test_smart_plotting_is_disabled_for_evaluation(self) -> None:
        for relative in (
            "agents/algorithm.toml",
            "agents/experiment.toml",
        ):
            with self.subTest(agent=relative):
                text = text_for(relative)
                prompt = prompt_for(relative)
                self.assertNotIn("smart-plotting", prompt)
                self.assertNotIn("Alg_Exp/picture/", prompt)
                self.assertNotRegex(
                    text,
                    r'(?m)^path = "[^\n]*smart-plotting/SKILL\.md"$',
                )

        workflow = text_for(
            "skills/reasflow/algorithm/algorithm-prototyping-workflow/SKILL.md"
        )
        self.assertNotIn("smart-plotting", workflow)
        self.assertNotIn("Alg_Exp/picture/", workflow)


if __name__ == "__main__":
    unittest.main()
