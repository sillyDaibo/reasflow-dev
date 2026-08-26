from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).parents[1]
SCRIPT = ROOT / "skills/reasflow/survey/codex-first-survey/scripts/codex_first_tools.py"
SPEC = importlib.util.spec_from_file_location("codex_first_tools", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_merge_uses_doi_arxiv_and_title_as_canonical_aliases() -> None:
    papers = [
        {
            "title": "Error Feedback Fixes SignSGD",
            "authors": [{"name": "Sai Praneeth Karimireddy"}],
            "year": 2019,
            "externalIds": {"DOI": "10.48550/arXiv.1901.09847"},
            "abstract": "short",
            "source": "semantic_scholar",
        },
        {
            "title": "Error Feedback Fixes SignSGD",
            "authors": ["Sai Praneeth Karimireddy"],
            "year": 2019,
            "externalIds": {"ArXiv": "1901.09847"},
            "abstract": "a substantially longer structured abstract",
            "source": "reascholar",
        },
    ]

    merged, conflicts = MODULE.merge_records(papers)

    assert len(merged) == 1
    assert merged[0]["abstract"] == "a substantially longer structured abstract"
    assert set(merged[0]["sources"]) == {"semantic_scholar", "reascholar"}
    assert merged[0]["bib_key"].startswith("karimireddy2019")
    assert conflicts == []


def test_shortlist_penalizes_known_topic_ambiguity(tmp_path) -> None:
    registry = tmp_path / "registry.jsonl"
    MODULE.write_jsonl(
        registry,
        [
            {
                "id": "good",
                "title": "Error Feedback in Distributed Optimization",
                "abstract": "Compressed stochastic gradients and residual accumulation.",
            },
            {
                "id": "bad",
                "title": "Error Feedback Control for Electric Power Grids",
                "abstract": "A controller for voltage regulation.",
            },
        ],
    )
    output = tmp_path / "shortlist.json"
    args = SimpleNamespace(
        registry=registry,
        state=None,
        query="error feedback distributed optimization",
        include_term=["compressed gradient"],
        exclude_term=["electric power grid"],
        limit=10,
        min_score=0.5,
        max_abstract_chars=200,
        output=output,
    )

    MODULE.command_shortlist(args)
    result = json.loads(output.read_text(encoding="utf-8"))

    assert [paper["id"] for paper in result["papers"]] == ["good"]


def test_structure_returns_only_mapped_resolved_candidates(tmp_path) -> None:
    ledger = tmp_path / "ledger.json"
    ledger.write_text(
        json.dumps(
            {
                "items": [
                    {
                        "id": "ok",
                        "kind": "timeline",
                        "candidate_claim": "A supported transition",
                        "support_paper_keys": ["p1", "p2"],
                        "unresolved_support_paper_ids": [],
                        "verification_status": "mapped_details_retrieved_still_requires_claim_check",
                    },
                    {
                        "id": "unresolved",
                        "kind": "timeline",
                        "candidate_claim": "An unsupported transition",
                        "support_paper_keys": ["p3"],
                        "unresolved_support_paper_ids": ["missing"],
                        "verification_status": "mapped_details_retrieved_still_requires_claim_check",
                    },
                ]
            }
        ),
        encoding="utf-8",
    )
    output = tmp_path / "structure.json"

    MODULE.command_structure(SimpleNamespace(ledger=ledger, kind="timeline", limit=10, output=output))
    result = json.loads(output.read_text(encoding="utf-8"))

    assert [item["id"] for item in result["candidates"]] == ["ok"]
    assert result["candidates"][0]["allowed_use"] == "research_hypothesis_requiring_paper_check"


def test_audit_keeps_publication_and_evidence_limits_explicit(tmp_path) -> None:
    state = tmp_path / "state.json"
    state.write_text(json.dumps({"topic": "Example", "profile": "s2-only"}), encoding="utf-8")
    registry = tmp_path / "registry.jsonl"
    records = []
    for index in range(105):
        records.append(
            {
                "title": f"Paper {index}",
                "authors": [f"Author {index}"],
                "year": 2020,
                "externalIds": {"ArXiv": f"2001.{index:05d}"},
                "bib_key": f"p{index}",
            }
        )
    MODULE.write_jsonl(registry, records)
    survey = tmp_path / "survey.tex"
    survey.write_text("\\citep{" + ",".join(f"p{i}" for i in range(101)) + "}", encoding="utf-8")
    related = tmp_path / "related.tex"
    related.write_text("\\citep{" + ",".join(f"p{i}" for i in range(50)) + "}", encoding="utf-8")
    bib = tmp_path / "references.bib"
    bib.write_text("\n".join(f"@misc{{p{i}, title={{Paper {i}}}}}" for i in range(105)), encoding="utf-8")
    output = tmp_path / "audit.json"

    code = MODULE.command_audit(
        SimpleNamespace(
            state=state, registry=registry, survey=survey, related=related,
            bib=bib, output=output,
        )
    )
    result = json.loads(output.read_text(encoding="utf-8"))

    assert code == 0
    assert result["gate_passed"] is True
    assert "does not establish claim-citation entailment" in result["limitations"][0]


def test_doi_validation_rejects_identifier_for_another_paper(tmp_path, monkeypatch) -> None:
    registry = tmp_path / "registry.jsonl"
    MODULE.write_jsonl(
        registry,
        [
            {
                "title": "Error Feedback Fixes SignSGD",
                "authors": ["Researcher"],
                "year": 2019,
                "externalIds": {"DOI": "10.1000/wrong"},
                "url": "https://doi.org/10.1000/wrong",
                "bib_key": "researcher2019error",
            }
        ],
    )
    monkeypatch.setattr(
        MODULE,
        "fetch_crossref",
        lambda doi, timeout: {
            "title": ["A Completely Unrelated Paper on Power Grid Control"],
            "author": [{"given": "Other", "family": "Author"}],
            "issued": {"date-parts": [[2020]]},
        },
    )
    output_registry = tmp_path / "validated.jsonl"
    report = tmp_path / "doi_report.json"

    code = MODULE.command_validate_doi(
        SimpleNamespace(
            registry=registry,
            output_registry=output_registry,
            report=report,
            min_title_similarity=0.65,
            timeout=1.0,
        )
    )
    record = MODULE.load_records(output_registry)[0]
    result = json.loads(report.read_text(encoding="utf-8"))

    assert code == 2
    assert MODULE.paper_doi(record) == ""
    assert record["rejected_identifiers"][0]["reason"] == "crossref_title_mismatch"
    assert result["rejected"] == 1


def test_doi_validation_can_be_limited_to_cited_records(tmp_path, monkeypatch) -> None:
    registry = tmp_path / "registry.jsonl"
    MODULE.write_jsonl(
        registry,
        [
            {
                "title": f"Paper {key}",
                "authors": ["Researcher"],
                "year": 2020,
                "externalIds": {"DOI": f"10.1000/{key}"},
                "bib_key": key,
            }
            for key in ("cited", "unused")
        ],
    )
    manuscript = tmp_path / "survey.tex"
    manuscript.write_text(r"\citep{cited}", encoding="utf-8")
    requested = []

    def fake_crossref(doi, timeout):
        requested.append(doi)
        return {"title": ["Paper cited"]}

    monkeypatch.setattr(MODULE, "fetch_crossref", fake_crossref)
    output_registry = tmp_path / "validated.jsonl"
    report = tmp_path / "doi_report.json"

    code = MODULE.command_validate_doi(
        SimpleNamespace(
            registry=registry,
            cited_from=[manuscript],
            output_registry=output_registry,
            report=report,
            min_title_similarity=0.65,
            timeout=1.0,
        )
    )

    assert code == 0
    assert requested == ["10.1000/cited"]
    assert [record["bib_key"] for record in MODULE.load_records(output_registry)] == ["cited"]


def test_bibtex_uses_identifiers_without_printing_per_entry_urls() -> None:
    entry = MODULE.bib_entry(
        {
            "bib_key": "researcher2020paper",
            "title": "A Paper",
            "authors": ["A. Researcher"],
            "year": 2020,
            "venue": "A Conference",
            "externalIds": {"DOI": "10.1000/example", "ArXiv": "2001.00001"},
        }
    )

    assert "doi = {10.1000/example}" in entry
    assert "url =" not in entry
    assert "https://" not in entry


def test_default_survey_agent_has_no_worker_or_frozen_prompt_contract() -> None:
    agent = (ROOT / "agents/survey.toml").read_text(encoding="utf-8")

    assert "survey-outline" not in agent
    assert "survey-section-writer" not in agent
    assert "survey-related-works" not in agent
    assert "150000" not in agent
    assert "max-papers 140" not in agent
    assert "do not delegate" in agent
