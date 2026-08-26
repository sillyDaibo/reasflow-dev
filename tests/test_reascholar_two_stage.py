from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace


SCRIPT = (
    Path(__file__).parents[1]
    / "skills/reasflow/survey/reascholar-two-stage-retrieval/scripts/two_stage_retrieval.py"
)
SPEC = importlib.util.spec_from_file_location("two_stage_retrieval", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_shared_s2_cache_freezes_identical_requests(tmp_path, monkeypatch) -> None:
    calls = []

    def fake_request(base, path, *, params, s2):
        calls.append((base, path, params, s2))
        return {"data": [{"paperId": "stable"}]}

    monkeypatch.setenv("REASFLOW_SHARED_S2_CACHE_DIR", str(tmp_path))
    monkeypatch.setattr(MODULE, "request_json", fake_request)
    args = SimpleNamespace(year_from=None, year_to=None, per_query=15)

    first = MODULE.search_s2("same query", args)
    second = MODULE.search_s2("same query", args)

    assert first == second
    assert len(calls) == 1
    assert len(list(tmp_path.glob("*.json"))) == 1


def test_domain_selector_uses_explicit_taxonomy_lexical_score() -> None:
    args = SimpleNamespace(domain_id=[], domain_count=1)
    discovery = {
        "domains": [
            {
                "domain_id": 10,
                "title": "Hierarchical",
                "score": 0.8,
                "score_breakdown": {
                    "topic_relevance": 0.8,
                    "lexical_match_score": 0.0,
                },
                "anchor_papers": [],
            },
            {
                "domain_id": 16,
                "title": "Bilevel",
                "score": 0.7,
                "score_breakdown": {
                    "topic_relevance": 0.5,
                    "lexical_match_score": 1.0,
                },
                "anchor_papers": [],
            },
        ]
    }
    selected = MODULE.select_domains(
        discovery,
        "Bilevel optimization methods and convergence assumptions",
        args,
    )
    assert selected[0]["title"] == "Bilevel"


def test_domain_selector_does_not_pad_with_generic_neighbors() -> None:
    args = SimpleNamespace(domain_id=[], domain_count=4)
    discovery = {
        "domains": [
            {
                "domain_id": 119,
                "title": "Quantized",
                "score": 0.9,
                "score_breakdown": {
                    "topic_relevance": 0.60,
                    "lexical_match_score": 1.0,
                },
                "anchor_papers": [],
            },
            {
                "domain_id": 53,
                "title": "Inexact",
                "score": 0.9,
                "score_breakdown": {
                    "topic_relevance": 0.54,
                    "lexical_match_score": 1.0,
                },
                "anchor_papers": [],
            },
            {
                "domain_id": 16,
                "title": "Synchronous",
                "description": "Communication and execution",
                "score": 0.57,
                "score_breakdown": {
                    "topic_relevance": 0.66,
                    "lexical_match_score": 0.2,
                },
                "anchor_papers": [],
            },
        ]
    }

    selected = MODULE.select_domains(
        discovery,
        "Quantized communication and inexact information exchange",
        args,
    )

    assert {item["title"] for item in selected} == {"Quantized", "Inexact"}


def test_domain_selector_prioritizes_specific_domain_over_generic_labels() -> None:
    args = SimpleNamespace(domain_id=[], domain_count=3)
    discovery = {
        "domains": [
            {
                "domain_id": 94,
                "title": "Convergence",
                "score": 0.9,
                "score_breakdown": {
                    "topic_relevance": 0.72,
                    "lexical_match_score": 1.0,
                },
                "anchor_papers": [],
                "rank": 1,
            },
            {
                "domain_id": 22,
                "title": "Stochastic",
                "score": 0.9,
                "score_breakdown": {
                    "topic_relevance": 0.70,
                    "lexical_match_score": 1.0,
                },
                "anchor_papers": [],
                "rank": 2,
            },
            {
                "domain_id": 84,
                "title": "Bilevel",
                "score": 0.9,
                "score_breakdown": {
                    "topic_relevance": 0.66,
                    "lexical_match_score": 1.0,
                },
                "anchor_papers": [],
                "rank": 3,
            },
        ]
    }

    selected = MODULE.select_domains(
        discovery,
        "Bilevel optimization methods, stochastic formulations, and convergence assumptions",
        args,
    )

    assert [item["title"] for item in selected] == ["Bilevel"]


def test_domain_selector_normalizes_variational_inequality_plural() -> None:
    args = SimpleNamespace(domain_id=[], domain_count=3)
    discovery = {
        "domains": [
            {
                "domain_id": 16,
                "title": "Synchronous",
                "score": 0.55,
                "score_breakdown": {
                    "topic_relevance": 0.61,
                    "lexical_match_score": 0.14,
                },
                "anchor_papers": [],
                "rank": 1,
            },
            {
                "domain_id": 58,
                "title": "Variational inequality",
                "score": 0.49,
                "score_breakdown": {
                    "topic_relevance": 0.61,
                    "lexical_match_score": 0.14,
                },
                "anchor_papers": [],
                "rank": 7,
            },
        ]
    }

    selected = MODULE.select_domains(
        discovery,
        "Variational inequalities in decentralized optimization and games",
        args,
    )

    assert [item["title"] for item in selected] == ["Variational inequality"]


def test_task_cutoff_and_final_year_filter(tmp_path) -> None:
    task = tmp_path / "task.yaml"
    task.write_text("cutoff_date: 2026-07-31\n", encoding="utf-8")

    assert MODULE.load_task_cutoff_year(task) == 2026
    assert MODULE.load_task_cutoff_date(task).isoformat() == "2026-07-31"
    assert MODULE.paper_within_year_bounds({"year": 2026}, None, 2026)
    assert not MODULE.paper_within_year_bounds({"year": 2099}, None, 2026)
    assert MODULE.paper_within_year_bounds({"year": None}, None, 2026)
    cutoff = MODULE.load_task_cutoff_date(task)
    assert MODULE.paper_within_date_cutoff(
        {"year": 2026, "publicationDate": "2026-07-31"}, cutoff
    )
    assert not MODULE.paper_within_date_cutoff(
        {"year": 2026, "publicationDate": "2026-08-01"}, cutoff
    )
    assert MODULE.paper_within_date_cutoff(
        {"year": 2026, "externalIds": {"ArXiv": "2607.12345"}}, cutoff
    )
    assert not MODULE.paper_within_date_cutoff(
        {"year": 2026, "externalIds": {"ArXiv": "2608.12345"}}, cutoff
    )
    assert not MODULE.paper_within_date_cutoff({"year": 2026}, cutoff)
    assert not MODULE.paper_within_date_cutoff({"year": None}, cutoff)


def test_explicit_domain_order_is_preserved() -> None:
    args = SimpleNamespace(domain_id=[104, 2, 34], domain_count=3)
    discovery = {
        "domains": [
            {"domain_id": 2, "title": "Proximal"},
            {"domain_id": 34, "title": "Saddle point"},
            {"domain_id": 104, "title": "Extragradient"},
        ]
    }

    selected = MODULE.select_domains(discovery, "Extragradient methods", args)

    assert [item["domain_id"] for item in selected] == [104, 2, 34]


def test_secondary_domain_support_requires_topic_overlap() -> None:
    selected_domains = [
        {"domain_id": 119, "title": "Quantized", "rank": 1},
        {"domain_id": 53, "title": "Inexact", "rank": 2},
    ]
    papers = [
        {
            "paper_key": "primary",
            "title": "General quantizer analysis",
            "support_domain_id": 119,
        },
        {
            "paper_key": "primary-unrelated",
            "title": "A generic proximal method for convex programming",
            "support_domain_id": 119,
        },
        {
            "paper_key": "primary-indirect-narrative",
            "title": "Distributed Algorithms with Finite Data Rates",
            "year": 2019,
            "support_domain_id": 119,
            "support_kind": "domain_narrative_support",
        },
        {
            "paper_key": "secondary-relevant",
            "title": "Inexact communication for distributed optimization",
            "support_domain_id": 53,
        },
        {
            "paper_key": "secondary-unrelated",
            "title": "A nonsmooth inexact Newton method with Hessian information",
            "support_domain_id": 53,
        },
        {
            "paper_key": "unknown-provenance",
            "title": "Quantized communication without source provenance",
        },
    ]

    kept = MODULE.select_topic_support_papers(
        papers,
        selected_domains,
        "Quantized communication and inexact information exchange in distributed optimization",
    )

    assert [paper["paper_key"] for paper in kept] == [
        "primary",
        "primary-indirect-narrative",
        "secondary-relevant",
    ]


def test_domain_scaffold_tags_top_papers_with_support_domain() -> None:
    details = [
        {
            "domain_id": 53,
            "title": "Inexact",
            "display": {
                "top_papers": [
                    {"paper_key": "generic-inexact", "title": "Inexact Newton"}
                ]
            },
        }
    ]

    _, support = MODULE.build_domain_scaffold(details)

    assert support == [
        {
            "paper_key": "generic-inexact",
            "title": "Inexact Newton",
            "support_domain_id": 53,
            "support_kind": "domain_top_paper",
        }
    ]


def test_detail_budget_prioritizes_search_then_primary_support() -> None:
    keys = MODULE.prioritize_detail_candidates(
        [
            {"paper_key": "search-a"},
            {"paper_key": "shared"},
        ],
        [
            {"paper_key": "secondary", "support_domain_id": 53},
            {"paper_key": "primary", "support_domain_id": 119},
            {"paper_key": "shared", "support_domain_id": 119},
        ],
        [{"domain_id": 119}, {"domain_id": 53}],
    )

    assert keys == ["search-a", "shared", "primary", "secondary"]


def test_merge_papers_deduplicates_arxiv_and_preserves_routes() -> None:
    left = {
        "title": "A useful paper",
        "year": 2024,
        "externalIds": {"ArXiv": "2401.12345"},
        "sources": ["reascholar"],
        "retrieval_routes": ["domain_support"],
        "citationCount": 0,
    }
    right = {
        "title": "A useful paper",
        "year": 2024,
        "externalIds": {"ArXiv": "2401.12345v2"},
        "sources": ["semantic_scholar"],
        "retrieval_routes": ["semantic_scholar:q4"],
        "citationCount": 12,
        "abstract": "Evidence-bearing abstract.",
    }

    merged = MODULE.merge_papers([left, right])

    assert len(merged) == 1
    assert merged[0]["citationCount"] == 12
    assert merged[0]["abstract"] == "Evidence-bearing abstract."
    assert merged[0]["sources"] == ["reascholar", "semantic_scholar"]


def test_merge_papers_resolves_transitive_cross_source_identity() -> None:
    papers = [
        {
            "title": "Canonical Optimization Paper",
            "year": 2024,
            "externalIds": {"DOI": "10.1000/example", "ArXiv": "2401.12345"},
            "sources": ["semantic_scholar"],
        },
        {
            "title": "Canonical Optimization Paper",
            "year": 2024,
            "externalIds": {"ArXiv": "2401.12345v2"},
            "sources": ["reascholar"],
            "paper_key": "2401.12345__2024__Canonical_Optimization_Paper",
        },
        {
            "title": "Canonical Optimization Paper",
            "year": 2024,
            "externalIds": {"DOI": "https://doi.org/10.1000/example"},
            "sources": ["semantic_scholar"],
        },
    ]

    merged = MODULE.merge_papers(papers)

    assert len(merged) == 1
    assert MODULE.duplicate_identity_tokens(merged) == {}
    assert merged[0]["sources"] == ["semantic_scholar", "reascholar"]


def test_citation_expansion_is_bounded_and_records_direction() -> None:
    details = []
    for seed_index in range(20):
        details.append(
            {
                "paper_key": f"seed-{seed_index}",
                "title": f"Seed {seed_index}",
                "display": {
                    "overview": {
                        "citations": {
                            "references": [
                                {"paper_key": f"ref-{seed_index}-{i}", "title": f"Reference {seed_index} {i}"}
                                for i in range(8)
                            ],
                            "cited_by": [
                                {"paper_key": f"citing-{seed_index}-{i}", "title": f"Citing {seed_index} {i}"}
                                for i in range(8)
                            ],
                        }
                    }
                },
            }
        )

    expanded, records = MODULE.expand_citation_neighbors(
        details,
        [{"paper_key": "ref-0-0", "title": "Reference 0 0"}],
    )

    assert len(expanded) == 30
    assert len(records) == 30
    assert len({record["expanded_paper_key"] for record in records}) == 30
    assert {record["direction"] for record in records} == {"reference", "cited_by"}
    assert all(record["hop"] == 1 for record in records)
    assert all(int(record["seed_paper_key"].split("-")[-1]) < 12 for record in records)
    assert "ref-0-0" not in {record["expanded_paper_key"] for record in records}


def test_empty_citation_details_do_not_consume_seed_budget() -> None:
    details = [
        {
            "paper_key": f"empty-{index}",
            "title": f"Empty {index}",
            "display": {"overview": {"citations": {}}},
        }
        for index in range(20)
    ]
    details.append(
        {
            "paper_key": "useful-seed",
            "title": "Useful Seed",
            "display": {
                "overview": {
                    "citations": {
                        "references": [
                            {"paper_key": "useful-ref", "title": "Useful Reference"}
                        ]
                    }
                }
            },
        }
    )

    expanded, records = MODULE.expand_citation_neighbors(
        details,
        [],
        max_seeds=1,
        backward_per_seed=1,
        forward_per_seed=0,
        max_new_papers=1,
    )

    assert [paper["paper_key"] for paper in expanded] == ["useful-ref"]
    assert records[0]["seed_paper_key"] == "useful-seed"


def test_citation_expansion_rejects_same_word_unrelated_branch() -> None:
    details = [
        {
            "paper_key": "seed",
            "title": "Quantized Distributed Optimization",
            "display": {
                "overview": {
                    "citations": {
                        "references": [
                            {
                                "paper_key": "relevant",
                                "title": "Distributed Consensus with Communication Compression",
                            },
                            {
                                "paper_key": "wrong-branch",
                                "title": "Computational Complexity of Stochastic Programming",
                            },
                        ]
                    }
                }
            },
        }
    ]
    relevance_terms = MODULE.match_token_set(
        "quantized communication distributed consensus bit complexity stochastic quantizer"
    ) - MODULE.match_token_set("complexity stochastic")

    expanded, _ = MODULE.expand_citation_neighbors(
        details,
        [],
        relevance_terms=relevance_terms,
        primary_domain_terms=MODULE.match_token_set("quantized"),
    )

    assert [paper["paper_key"] for paper in expanded] == ["relevant"]


def test_semantic_scholar_identifier_prefers_canonical_external_ids() -> None:
    assert MODULE.semantic_scholar_identifier(
        {"externalIds": {"DOI": "https://doi.org/10.1000/EXAMPLE"}}
    ) == "DOI:10.1000/example"
    assert MODULE.semantic_scholar_identifier(
        {"externalIds": {"ArXiv": "2005.10785v2"}}
    ) == "ARXIV:2005.10785"


def test_sparse_local_graph_uses_bounded_s2_citation_fallback() -> None:
    requests = []

    def fetch(path, params):
        requests.append((path, params))
        if path.endswith("/references"):
            return {
                "data": [
                    {
                        "citedPaper": {
                            "paperId": "reference",
                            "title": "Foundations of Heavy-Tailed Gradient Clipping",
                            "year": 2020,
                            "publicationDate": "2020-05-01",
                        }
                    }
                ]
            }
        return {
            "data": [
                {
                    "citingPaper": {
                        "paperId": "successor",
                        "title": "Adaptive Optimization under Heavy-Tailed Noise",
                        "year": 2025,
                        "publicationDate": "2025-06-01",
                    }
                }
            ]
        }

    seed = {
        "paper_key": "2005.10785__seed",
        "title": "Stochastic Optimization with Heavy-Tailed Noise",
        "externalIds": {"ArXiv": "2005.10785"},
    }
    expanded, records, audit = MODULE.expand_s2_citation_neighbors(
        [seed],
        [seed],
        max_seeds=1,
        backward_per_seed=1,
        forward_per_seed=1,
        max_new_papers=2,
        relevance_terms=MODULE.match_token_set("heavy tailed noise clipping adaptive"),
        primary_domain_terms=MODULE.match_token_set("heavy tailed noise"),
        year_from=None,
        year_to=2026,
        cutoff_date=MODULE.date(2026, 7, 31),
        fetch=fetch,
    )

    assert [paper["paperId"] for paper in expanded] == ["reference", "successor"]
    assert {record["provider"] for record in records} == {"semantic_scholar"}
    assert len(audit) == 2
    assert all(record["retained"] == 1 for record in audit)
    assert requests[0][0] == "/paper/ARXIV:2005.10785/references"


def test_s2_citation_fallback_tolerates_explicit_null_data() -> None:
    seed = {
        "paper_key": "2005.10785__seed",
        "title": "Stochastic Optimization with Heavy-Tailed Noise",
        "externalIds": {"ArXiv": "2005.10785"},
    }

    expanded, records, audit = MODULE.expand_s2_citation_neighbors(
        [seed],
        [seed],
        max_seeds=1,
        backward_per_seed=1,
        forward_per_seed=1,
        max_new_papers=2,
        relevance_terms=MODULE.match_token_set("heavy tailed noise clipping adaptive"),
        primary_domain_terms=MODULE.match_token_set("heavy tailed noise"),
        year_from=None,
        year_to=2026,
        cutoff_date=MODULE.date(2026, 7, 31),
        fetch=lambda _path, _params: {"data": None},
    )

    assert expanded == []
    assert records == []
    assert len(audit) == 2
    assert all(item["status"] == "ok" for item in audit)
    assert all(item["returned"] == 0 for item in audit)
    assert all(item["retained"] == 0 for item in audit)


def test_search_relevance_requires_primary_or_two_topic_signatures() -> None:
    primary = MODULE.match_token_set("Quantized")
    signature = MODULE.match_token_set(
        "quantized communication information exchange distributed optimization"
    ) - MODULE.match_token_set("information optimization")

    assert MODULE.search_candidate_relevant(
        "Quantization Design for Distributed Optimization", primary, signature
    )
    assert MODULE.search_candidate_relevant(
        "Communication-Efficient Distributed Learning", primary, signature
    )
    assert not MODULE.search_candidate_relevant(
        "DINGO: Distributed Newton-Type Method for Gradient-Norm Optimization",
        primary,
        signature,
    )


def test_stage_queries_compact_generic_long_topic_prefixes() -> None:
    topic = "Evolution and comparative foundations of decentralized optimization over networks"
    assert MODULE.stage_queries(topic) == [
        "decentralized optimization networks",
        "decentralized optimization networks algorithms",
        "decentralized optimization networks convergence",
        "decentralized optimization networks survey",
    ]


def test_task_aware_stage_queries_cover_expected_aspects(tmp_path) -> None:
    task = tmp_path / "task.yaml"
    task.write_text(
        """expected_aspects:
  - {name: Correction mechanisms, keywords: [error feedback, residual, compression]}
  - {name: Perturbation sources, keywords: [quantization, clipping, differential privacy]}
  - {name: Rates and tradeoffs, keywords: [convergence rate, communication, privacy]}
""",
        encoding="utf-8",
    )

    queries = MODULE.stage_queries(
        "Error-feedback mechanisms for compressed, clipped, and private distributed optimization",
        task,
    )

    assert len(queries) == 4
    assert queries[0] == "error feedback compressed clipped private"
    assert "residual" in queries[1]
    assert "quantization" in queries[2]
    assert "convergence" in queries[3]


def test_required_anchor_audit_keeps_only_exact_title_matches(
    tmp_path, monkeypatch
) -> None:
    def fake_search(query, args, limit=None):
        assert limit == 10
        return {
            "data": [
                {"paperId": "near", "title": "Distributed Subgradient Variants"},
                {
                    "paperId": "exact",
                    "title": "Distributed Subgradient Methods for Multi-Agent Optimization",
                    "authors": [{"name": "A. Author"}],
                    "year": 2009,
                },
            ]
        }

    monkeypatch.setattr(MODULE, "search_s2", fake_search)
    papers, audit, query_count = MODULE.audit_required_s2_anchors(
        [
            {
                "title": "Distributed Subgradient Methods for Multi-Agent Optimization",
                "aliases": ["distributed subgradient methods"],
            }
        ],
        SimpleNamespace(),
        tmp_path,
    )

    assert query_count == 1
    assert [paper["paperId"] for paper in papers] == ["exact"]
    assert audit[0]["status"] == "resolved_exact_title"
    assert audit[0]["resolved_title"] == papers[0]["title"]


def test_domain_scaffold_labels_every_claim_provisional() -> None:
    details = [
        {
            "domain_id": 7,
            "title": "Example Domain",
            "paper_count": 20,
            "display": {
                "overview": {"description": "A candidate map."},
                "provenance": {"status": "complete"},
                "timeline": [
                    {
                        "title": "First phase",
                        "description": "A synthesized chronology.",
                        "support_papers": [
                            {"paper_key": "2401.00001__2024__Paper", "title": "Paper"}
                        ],
                        "unresolved_support_paper_ids": ["legacy-id"],
                    }
                ],
                "limitations": [],
                "future_works": [],
                "top_papers": [],
            },
        }
    ]

    scaffold, support = MODULE.build_domain_scaffold(details)

    assert scaffold["role"] == "candidate_scaffold_only"
    assert len(support) == 1
    item = scaffold["narrative_items"][0]
    assert item["allowed_outline_use"] == "provisional_scaffold_only"
    assert item["verification_status"].startswith("candidate_pending")
    assert item["unresolved_support_paper_ids"] == ["legacy-id"]


def test_domain_scaffold_rejects_conclusions_mislabeled_as_future_work() -> None:
    future = {
        "direction": "The method converges at the optimal rate.",
        "support_papers": [{"paper_key": "paper-a", "title": "Paper A"}],
    }
    valid_future = {
        "direction": "Study delayed heavy-tailed updates.",
        "why_now": "The supplied theorem assumes synchronous messages.",
        "first_step": "Vary delay and tail index independently.",
        "support_papers": [{"paper_key": "paper-b", "title": "Paper B"}],
    }
    details = [
        {
            "domain_id": 7,
            "title": "Example Domain",
            "paper_count": 20,
            "display": {
                "overview": {},
                "provenance": {},
                "timeline": [],
                "limitations": [],
                "future_works": [future, future, valid_future, valid_future],
                "top_papers": [],
            },
        }
    ]

    scaffold, _ = MODULE.build_domain_scaffold(details)

    rows = [
        item
        for item in scaffold["narrative_items"]
        if item["kind"] == "future_work"
    ]
    assert len(rows) == 1
    assert rows[0]["why_now"] == valid_future["why_now"]
    assert rows[0]["first_step"] == valid_future["first_step"]


def test_structure_pack_keeps_unresolved_support_out_of_evidence() -> None:
    scaffold = {
        "domains": [
            {
                "domain_id": 7,
                "title": "Example Domain",
                "l1_name_en": "Optimization",
                "paper_count": 2,
                "overview": {"description": "A candidate taxonomy branch."},
            }
        ]
    }
    ledger = [
        {
            "id": "domain-7-timeline-1",
            "kind": "timeline",
            "domain_id": 7,
            "domain_title": "Example Domain",
            "candidate_claim": "Paper A preceded Paper B.",
            "period_start": 2020,
            "period_end": 2021,
            "support_paper_keys": ["paper-a", "missing-paper"],
            "support_paper_titles": ["Paper A", "Missing Paper"],
            "unresolved_support_paper_ids": ["legacy-id"],
            "verification_status": "mapped_details_retrieved_still_requires_claim_check",
        }
    ]
    papers = [
        {"paper_key": "paper-a", "title": "Paper A", "year": 2020},
        {"paper_key": "paper-b", "title": "Paper B", "year": 2021},
    ]
    details = [
        {
            "paper_key": "paper-b",
            "display": {
                "overview": {
                    "citations": {
                        "references": [
                            {"paper_key": "paper-a", "title": "Paper A"}
                        ],
                        "cited_by": [],
                    }
                }
            },
        }
    ]

    pack = MODULE.build_structure_pack(scaffold, ledger, papers, details)

    assert pack["schema_version"] == "reascholar-structure-pack-v1"
    assert [item["paper_key"] for item in pack["timeline"][0]["support_papers"]] == [
        "paper-a"
    ]
    assert pack["citation_relations"][0]["citing_paper_key"] == "paper-b"
    assert pack["citation_relations"][0]["cited_paper_key"] == "paper-a"
    warning = pack["warnings"][0]
    assert warning["unresolved_support_paper_ids"] == ["legacy-id"]
    assert warning["support_keys_absent_from_frozen_pool"] == ["missing-paper"]
    assert "legacy-id" not in json.dumps(pack["timeline"])


def test_s2_only_profile_never_calls_reascholar(tmp_path, monkeypatch) -> None:
    calls: list[tuple[str, str]] = []

    def fake_request(base, path, **kwargs):
        calls.append((base, path))
        assert base == MODULE.S2_BASE
        return {
            "data": [
                {
                    "paperId": path + str(len(calls)),
                    "title": f"Paper {len(calls)}",
                    "authors": [{"name": "A. Author"}],
                    "year": 2024,
                    "externalIds": {},
                }
            ]
        }

    monkeypatch.setattr(MODULE, "request_json", fake_request)
    args = SimpleNamespace(
        topic="controlled topic",
        profile="s2-only",
        out_dir=tmp_path,
        discover_only=False,
        domain_id=[],
        discovery_count=8,
        domain_count=3,
        search_depth=160,
        anchor_papers=3,
        per_query=2,
        max_details=20,
        year_from=None,
        year_to=None,
    )

    assert MODULE.run(args) == 0
    manifest = json.loads((tmp_path / "retrieval_manifest.json").read_text())
    assert manifest["profile"] == "s2-only"
    assert manifest["reascholar_base_url"] is None
    assert manifest["stage_two_query_budget"] == 4
    assert manifest["shared_s2_query_budget"] == 4
    assert manifest["additive_reascholar_query_budget"] == 0
    assert manifest["total_paper_search_query_budget"] == 4
    assert manifest["shared_s2_core_ok"] is True
    assert len(calls) == 4


def test_reascholar_profile_keeps_all_four_s2_core_queries(tmp_path, monkeypatch) -> None:
    s2_queries: list[str] = []

    monkeypatch.setattr(
        MODULE,
        "discover_domains",
        lambda topic, args: {"domains": []},
    )
    monkeypatch.setattr(MODULE, "select_domains", lambda discovery, topic, args: [])
    monkeypatch.setattr(MODULE, "fetch_domain_details", lambda selected: [])

    def fake_s2(query, args):
        s2_queries.append(query)
        return {
            "data": [
                {
                    "paperId": f"s2-{len(s2_queries)}",
                    "title": f"Core paper {len(s2_queries)}",
                    "authors": [{"name": "A. Author"}],
                    "year": 2024,
                    "externalIds": {},
                }
            ]
        }

    monkeypatch.setattr(MODULE, "search_s2", fake_s2)
    args = SimpleNamespace(
        topic="controlled topic",
        profile="reascholar-s2",
        out_dir=tmp_path,
        discover_only=False,
        domain_id=[],
        discovery_count=8,
        domain_count=3,
        search_depth=160,
        anchor_papers=3,
        per_query=2,
        max_details=20,
        year_from=None,
        year_to=None,
    )

    assert MODULE.run(args) == 0
    manifest = json.loads((tmp_path / "retrieval_manifest.json").read_text())
    assert s2_queries == MODULE.stage_queries("controlled topic")
    assert manifest["shared_s2_query_budget"] == 4
    assert manifest["additive_reascholar_query_budget"] == 3
    assert manifest["total_paper_search_query_budget"] == 7
    s2_records = [
        item for item in manifest["searches"] if item["provider"] == "semantic_scholar"
    ]
    assert len(s2_records) == 4
    assert {item["stratum"] for item in s2_records} == {"shared_s2_core"}
    assert manifest["shared_s2_core_ok"] is True


def test_domain_scaffold_tolerates_explicit_null_support_lists() -> None:
    details = [
        {
            "domain_id": 104,
            "title": "Extragradient",
            "l1_domain_id": 0,
            "l1_name_en": "Algorithm framework",
            "paper_count": 10,
            "display": {
                "overview": {},
                "provenance": {},
                "timeline": [
                    {
                        "title": "Early development",
                        "description": "A supported development period.",
                        "support_papers": None,
                        "unresolved_support_paper_ids": None,
                    }
                ],
                "limitations": [],
                "future_works": [],
                "top_papers": [],
            },
        }
    ]

    scaffold, ledger = MODULE.build_domain_scaffold(details)

    assert scaffold["domains"][0]["domain_id"] == 104
    assert ledger == []
