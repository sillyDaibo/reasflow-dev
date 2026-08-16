from __future__ import annotations

import argparse
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = (
    REPO_ROOT
    / "skills"
    / "reasflow"
    / "common"
    / "reascholar-evidence-retrieval"
    / "scripts"
    / "retrieve-evidence.py"
)


def load_module():
    spec = importlib.util.spec_from_file_location(
        "test_reascholar_evidence_module",
        SCRIPT_PATH,
    )
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load {SCRIPT_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


evidence = load_module()


def search_result() -> dict:
    return {
        "rank": 1,
        "result_type": "paper",
        "paper_key": (
            "2203.06735__2022__Private_Non-Convex_Federated_Learning_"
            "Without_a_Trusted_Server"
        ),
        "score": 0.621603,
        "title": "Private Non-Convex Federated Learning Without a Trusted Server",
        "authors": ["Andrew Lowy", "Ali Ghafelebashi", "Meisam Razaviyayn"],
        "year": 2022,
        "doi": (
            "2022__Private_Non-Convex_Federated_Learning_Without_a_Trusted_Server"
        ),
        "category": "distributed_optimization",
        "flags": {
            "has_algorithm": True,
            "has_theory": True,
            "has_experiments": True,
            "has_code_link": True,
            "has_prover": True,
        },
        "schema_match": {
            "preview": {
                "state_variables": [
                    {
                        "symbol": "h_r",
                        "role": "gradient_estimator",
                        "description": "Server-side gradient estimate.",
                    }
                ]
            }
        },
    }


def detail_response() -> dict:
    return {
        "paper_key": search_result()["paper_key"],
        "title": search_result()["title"],
        "links": {
            "markdown": f"/api/papers/{search_result()['paper_key']}/markdown"
        },
        "display": {
            "overview": {
                "publication": {
                    "year": 2022,
                    "authors": "Andrew Lowy; Ali Ghafelebashi; Meisam Razaviyayn",
                    "doi": search_result()["doi"],
                    "bibtex": (
                        "@misc{lowy2023private,\n"
                        "  title={Private Non-Convex Federated Learning},\n"
                        "  year={2023}\n"
                        "}"
                    ),
                }
            },
            "algorithm": {
                "problem": {
                    "task": "Private cross-silo federated learning.",
                    "setting": "Untrusted server.",
                    "objectives": ["Minimize a composite loss."],
                    "assumptions": ["The feasible set is closed and convex."],
                    "constraints": ["Protect record-level privacy."],
                },
                "method": {
                    "summary": "A private proximal SPIDER method.",
                    "variants": ["ISRL-DP FedProx-SPIDER"],
                    "initialization": ["Initialize w_0 and privacy noise."],
                    "update_rules": [
                        {
                            "name": "SPIDER refresh",
                            "formulas": ["h_r = average_i(h_r^i)"],
                            "explanation": "Refresh the noisy gradient estimator.",
                            "uses": ["procedure_6"],
                        }
                    ],
                    "design_choices": [
                        {
                            "choice": "Use variance reduction.",
                            "rationale": "Reduce stochastic variance.",
                        }
                    ],
                    "implementation": ["Clip gradients before adding noise."],
                },
                "code_snippets": [
                    {
                        "target_label": "spider_epoch_refresh",
                        "repo_url": "https://example.com/repo.git",
                        "file_path": "DP_FL2.py",
                        "start_line": 499,
                        "end_line": 547,
                        "language": "python",
                        "reason": "Matches SPIDER refresh.",
                        "code": "def spider_boost():\n    pass",
                    }
                ],
            },
            "experiment": {
                "datasets": [
                    {
                        "name": "MNIST",
                        "usage": "Even-vs-odd classification.",
                    }
                ],
                "baselines": [
                    {
                        "name": "FedAvg",
                        "role": "comparator_method",
                    }
                ],
                "setup": {
                    "environment": ["6-core Intel Core i7-8700"],
                    "parameters": ["epsilon in {0.75, 1, 3}"],
                },
                "evaluations": [
                    {
                        "name": "mnist_classification",
                        "goal": "Compare private FL methods.",
                        "metrics": ["test error"],
                        "settings": ["25 heterogeneous silos"],
                        "findings": ["The proposed method reports lower error."],
                    }
                ],
                "limitations": ["Large q values were not tested."],
            },
            "proof": {
                "statement_count_returned": 2,
                "has_more_statements": True,
                "statement_cards": [
                    {
                        "object_id": "template_macro",
                        "label": "IEEE proof environment macros",
                        "type": "definition",
                        "statement": "\\def\\IEEEQEDclosed{...}",
                        "raw": {
                            "qa_flags": [
                                "raw_line_fallback_after_empty_llm_card"
                            ]
                        },
                    },
                    {
                        "object_id": "theorem_1",
                        "label": "Theorem 1",
                        "type": "theorem",
                        "statement": "The iterates converge under Assumption 1.",
                        "context": {
                            "section_id": "s12",
                            "start_line": 120,
                            "end_line": 125,
                        },
                    },
                ],
                "dependency_edges": [
                    {
                        "source_object_id": "theorem_1",
                        "target_object_id": "assumption_1",
                        "relation": "uses",
                    }
                ],
            },
        },
    }


class NormalizationTests(unittest.TestCase):
    def test_algorithm_evidence_preserves_structure_and_quality_warnings(self) -> None:
        paper = evidence.normalize_algorithm_paper(
            search_result(),
            detail_response(),
            "Alg_Exp/evidence/raw/paper.json",
        )

        self.assertEqual(
            paper["algorithm"]["method"]["update_rules"][0]["name"],
            "SPIDER refresh",
        )
        self.assertEqual(
            paper["algorithm"]["method"]["state_variables"][0]["symbol"],
            "h_r",
        )
        self.assertEqual(paper["code_snippets"][0]["file_path"], "DP_FL2.py")
        self.assertIn("def spider_boost", paper["code_snippets"][0]["code_preview"])
        self.assertNotIn("code", paper["code_snippets"][0])
        self.assertEqual(
            paper["theory"]["statements"][0]["quality"],
            "rejected_template_content",
        )
        self.assertEqual(
            paper["theory"]["statements"][1]["quality"],
            "reviewed_extraction",
        )
        self.assertTrue(any("Year conflict" in item for item in paper["warnings"]))
        self.assertTrue(
            any("not a canonical DOI" in item for item in paper["warnings"])
        )
        self.assertTrue(
            any("LaTeX template content" in item for item in paper["warnings"])
        )
        self.assertEqual(paper["doi"], "")
        self.assertEqual(paper["arxiv_id"], "2203.06735")

    def test_experiment_evidence_labels_reported_findings(self) -> None:
        paper = evidence.normalize_experiment_paper(
            search_result(),
            detail_response(),
            "Alg_Exp/evidence/raw/paper.json",
        )

        experiment = paper["experiment"]
        self.assertEqual(experiment["datasets"][0]["name"], "MNIST")
        self.assertEqual(experiment["baselines"][0]["name"], "FedAvg")
        self.assertEqual(
            experiment["setup"]["environment"][0],
            "6-core Intel Core i7-8700",
        )
        self.assertNotIn("findings", experiment["evaluations"][0])
        self.assertEqual(
            experiment["evaluations"][0]["reported_findings"],
            ["The proposed method reports lower error."],
        )

    def test_theorem_hits_read_paper_identity_from_raw_result(self) -> None:
        hits = evidence.normalize_theorem_hits(
            {
                "results": [
                    {
                        "rank": 1,
                        "result_type": "statement",
                        "score": 0.7,
                        "label": "Theorem 2",
                        "statement_type": "theorem",
                        "statement": "The method converges linearly.",
                        "raw": {
                            "paper_key": "1234.56789__paper",
                            "title": "A Paper",
                            "object_id": "theorem_2",
                        },
                    },
                    {"result_type": "paper"},
                ]
            }
        )

        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0]["paper_key"], "1234.56789__paper")
        self.assertEqual(hits[0]["object_id"], "theorem_2")


class RetrievalTests(unittest.TestCase):
    def test_retrieval_writes_compact_raw_and_manifest_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir)
            args = evidence.build_parser().parse_args(
                [
                    "algorithm",
                    "--workspace",
                    str(workspace),
                    "--query",
                    "private federated optimization",
                    "--top-k",
                    "1",
                    "--detail-top-k",
                    "1",
                    "--no-theorem-search",
                ]
            )
            with (
                mock.patch.object(
                    evidence.literature,
                    "post_reascholar_json",
                    return_value={"results": [search_result()]},
                ),
                mock.patch.object(
                    evidence.literature,
                    "get_reascholar_json",
                    return_value=detail_response(),
                ),
            ):
                payload = evidence.retrieve_evidence(args)

            output = workspace / "Alg_Exp/evidence/algorithm_evidence.json"
            manifest = workspace / "Alg_Exp/evidence/retrieval_manifest.json"
            loaded = json.loads(output.read_text(encoding="utf-8"))
            loaded_manifest = json.loads(manifest.read_text(encoding="utf-8"))
            raw_detail = workspace / loaded["papers"][0]["sources"]["raw_response"]
            raw_search = workspace / loaded["raw_search_response"]
            self.assertEqual(payload["retrieval_status"], "ok")
            self.assertEqual(loaded["paper_detail_count"], 1)
            self.assertTrue(raw_detail.exists())
            self.assertTrue(raw_search.exists())
            self.assertEqual(len(loaded_manifest["runs"]), 1)
            self.assertEqual(
                loaded_manifest["runs"][0]["query"],
                "private federated optimization",
            )
            self.assertEqual(payload["cache"]["detail_network_fetches"], 1)
            self.assertFalse(payload["cache"]["search_cache_hit"])
            self.assertIn(
                loaded["papers"][0]["sources"]["raw_response"],
                loaded["raw_response_sha256"],
            )

    def test_repeat_query_reuses_search_and_detail_cache(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir)
            args = evidence.build_parser().parse_args(
                [
                    "algorithm",
                    "--workspace",
                    str(workspace),
                    "--query",
                    "private federated optimization",
                    "--top-k",
                    "1",
                    "--detail-top-k",
                    "1",
                    "--no-theorem-search",
                ]
            )
            with (
                mock.patch.object(
                    evidence.literature,
                    "post_reascholar_json",
                    return_value={"results": [search_result()]},
                ),
                mock.patch.object(
                    evidence.literature,
                    "get_reascholar_json",
                    return_value=detail_response(),
                ),
            ):
                evidence.retrieve_evidence(args)

            with (
                mock.patch.object(
                    evidence.literature,
                    "post_reascholar_json",
                    side_effect=AssertionError("search cache was not used"),
                ),
                mock.patch.object(
                    evidence.literature,
                    "get_reascholar_json",
                    side_effect=AssertionError("detail cache was not used"),
                ),
            ):
                payload = evidence.retrieve_evidence(args)

        self.assertTrue(payload["cache"]["search_cache_hit"])
        self.assertEqual(payload["cache"]["detail_cache_hits"], 1)
        self.assertEqual(payload["cache"]["detail_network_fetches"], 0)

    def test_experiment_reuses_algorithm_detail_response(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir)
            algorithm_args = evidence.build_parser().parse_args(
                [
                    "algorithm",
                    "--workspace",
                    str(workspace),
                    "--query",
                    "private federated optimization algorithm",
                    "--top-k",
                    "1",
                    "--detail-top-k",
                    "1",
                    "--no-theorem-search",
                ]
            )
            experiment_args = evidence.build_parser().parse_args(
                [
                    "experiment",
                    "--workspace",
                    str(workspace),
                    "--query",
                    "private federated optimization experiment",
                    "--top-k",
                    "1",
                    "--detail-top-k",
                    "1",
                ]
            )
            with (
                mock.patch.object(
                    evidence.literature,
                    "post_reascholar_json",
                    return_value={"results": [search_result()]},
                ),
                mock.patch.object(
                    evidence.literature,
                    "get_reascholar_json",
                    return_value=detail_response(),
                ),
            ):
                evidence.retrieve_evidence(algorithm_args)

            with (
                mock.patch.object(
                    evidence.literature,
                    "post_reascholar_json",
                    return_value={"results": [search_result()]},
                ),
                mock.patch.object(
                    evidence.literature,
                    "get_reascholar_json",
                    side_effect=AssertionError("algorithm detail was not reused"),
                ),
            ):
                payload = evidence.retrieve_evidence(experiment_args)

        self.assertEqual(payload["cache"]["detail_cache_hits"], 1)
        self.assertEqual(payload["cache"]["detail_network_fetches"], 0)
        self.assertEqual(
            payload["papers"][0]["experiment"]["datasets"][0]["name"],
            "MNIST",
        )

    def test_one_detail_failure_preserves_other_paper_evidence(self) -> None:
        failed_result = search_result()
        failed_result["paper_key"] = "2401.00001__failed"
        successful_result = search_result()
        successful_result["rank"] = 2

        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir)
            args = evidence.build_parser().parse_args(
                [
                    "experiment",
                    "--workspace",
                    str(workspace),
                    "--query",
                    "private federated optimization",
                    "--top-k",
                    "2",
                    "--detail-top-k",
                    "2",
                ]
            )
            with (
                mock.patch.object(
                    evidence.literature,
                    "post_reascholar_json",
                    return_value={
                        "results": [failed_result, successful_result]
                    },
                ),
                mock.patch.object(
                    evidence.literature,
                    "get_reascholar_json",
                    side_effect=[
                        RuntimeError("temporary detail failure"),
                        detail_response(),
                    ],
                ),
            ):
                payload = evidence.retrieve_evidence(args)

        self.assertEqual(payload["retrieval_status"], "partial")
        self.assertEqual(payload["paper_detail_count"], 1)
        self.assertTrue(
            any("2401.00001__failed" in warning for warning in payload["warnings"])
        )


if __name__ == "__main__":
    unittest.main()
