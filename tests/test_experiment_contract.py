from __future__ import annotations

import hashlib
import importlib.util
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = (
    REPO_ROOT
    / "skills/reasflow/experiment/experiment-design/scripts"
    / "validate-execution-contract.py"
)
SPEC = importlib.util.spec_from_file_location("experiment_contract", SCRIPT)
if SPEC is None or SPEC.loader is None:
    raise ImportError(SCRIPT)
contract_module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(contract_module)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def ready_contract(algorithm_path: Path, workspace: Path) -> dict:
    paper_key = "paper__accepted_for_task"
    return {
        "schema_version": "1.0",
        "status": "ready",
        "evidence_relevance": {
            "accepted_paper_keys": [paper_key],
            "rejected_papers": [],
        },
        "algorithm": {
            "implementation_path": str(algorithm_path.relative_to(workspace)),
            "implementation_sha256": sha256(algorithm_path),
            "entrypoint": "algorithm:OptimizationAlgorithm",
            "state_variables": ["x", "gradient_estimator"],
            "update_rules": [
                {
                    "name": "gradient step",
                    "formula": "x_next = x - eta * g",
                    "source": "paper",
                    "paper_key": paper_key,
                    "evidence_location": "Alg_Exp/evidence/raw/paper.json#update",
                }
            ],
            "proximal_or_projection": {
                "applicable": False,
                "reason": "The feasible set is unconstrained.",
            },
            "privacy": {
                "applicable": False,
                "reason": "The task has no privacy claim.",
            },
        },
        "experiment": {
            "datasets": [{"name": "synthetic quadratic", "source": "local_choice"}],
            "baselines": [{"name": "gradient descent", "source": "local_choice"}],
            "metrics": [
                {
                    "name": "objective gap",
                    "computation": "f(x)-f_star",
                    "source": "local_choice",
                }
            ],
            "seeds": [1, 2, 3],
            "budget": {
                "unit": "gradient evaluations",
                "limit": 1000,
                "fairness_rule": "equal evaluations for every method",
            },
            "commands": ["python Alg_Exp/code/experiment.py --seed 1"],
        },
        "unresolved_blockers": [],
    }


class ExecutionContractTests(unittest.TestCase):
    def test_ready_contract_passes(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            workspace = Path(temp)
            algorithm = workspace / "Alg_Exp/code/algorithm.py"
            algorithm.parent.mkdir(parents=True)
            algorithm.write_text(
                "class OptimizationAlgorithm:\n    def step(self, x, g):\n"
                "        return x - 0.1 * g\n",
                encoding="utf-8",
            )
            result = contract_module.validate_contract(
                ready_contract(algorithm, workspace),
                workspace,
                require_ready=True,
            )
        self.assertTrue(result["valid"])
        self.assertTrue(result["ready_for_execution"])

    def test_blocked_placeholder_is_valid_for_planning_but_not_execution(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            workspace = Path(temp)
            algorithm = workspace / "Alg_Exp/code/algorithm.py"
            algorithm.parent.mkdir(parents=True)
            algorithm.write_text(
                "def step(*args):\n    raise NotImplementedError('placeholder')\n",
                encoding="utf-8",
            )
            payload = ready_contract(algorithm, workspace)
            payload["status"] = "blocked"
            payload["unresolved_blockers"] = [
                "The algorithm update is not implemented."
            ]
            result = contract_module.validate_contract(payload, workspace)
            execution_result = contract_module.validate_contract(
                payload,
                workspace,
                require_ready=True,
            )
        self.assertTrue(result["valid"])
        self.assertFalse(result["ready_for_execution"])
        self.assertTrue(result["warnings"])
        self.assertFalse(execution_result["valid"])

    def test_ready_contract_rejects_changed_algorithm(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            workspace = Path(temp)
            algorithm = workspace / "Alg_Exp/code/algorithm.py"
            algorithm.parent.mkdir(parents=True)
            algorithm.write_text("x = 1\n", encoding="utf-8")
            payload = ready_contract(algorithm, workspace)
            algorithm.write_text("x = 2\n", encoding="utf-8")
            result = contract_module.validate_contract(
                payload,
                workspace,
                require_ready=True,
            )
        self.assertFalse(result["valid"])
        self.assertTrue(
            any("does not match" in error for error in result["errors"])
        )

    def test_paper_source_must_pass_relevance_gate(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            workspace = Path(temp)
            algorithm = workspace / "Alg_Exp/code/algorithm.py"
            algorithm.parent.mkdir(parents=True)
            algorithm.write_text("def step(x, g):\n    return x - g\n", encoding="utf-8")
            payload = ready_contract(algorithm, workspace)
            payload["evidence_relevance"]["accepted_paper_keys"] = []
            result = contract_module.validate_contract(
                payload,
                workspace,
                require_ready=True,
            )
        self.assertFalse(result["valid"])
        self.assertTrue(
            any("task-relevance gate" in error for error in result["errors"])
        )


if __name__ == "__main__":
    unittest.main()
