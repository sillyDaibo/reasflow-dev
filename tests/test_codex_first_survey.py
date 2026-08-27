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


def test_merge_and_inspect_preserve_reascholar_tags_and_profile(tmp_path) -> None:
    records = [
        {
            "id": "reascholar:paper",
            "title": "A Tagged Method",
            "authors": ["Researcher"],
            "year": 2024,
            "externalIds": {"DOI": "10.1000/tagged"},
            "source": "reascholar",
            "sources": ["reascholar"],
            "nine_dimensional_tags": {
                "algorithm": ["algorithm.extragradient"],
                "problem": ["problem.minimax"],
            },
            "domain_memberships": [
                {"domain_id": 104, "label": "Extragradient", "role": "core"}
            ],
            "profile_evidence": {
                "problem": {"task": "Solve a monotone inclusion."},
                "method": {"summary": "Use an extra-gradient correction."},
            },
        },
        {
            "id": "s2:paper",
            "title": "A Tagged Method",
            "authors": ["Researcher"],
            "year": 2024,
            "externalIds": {"DOI": "10.1000/tagged"},
            "source": "semantic_scholar",
            "sources": ["semantic_scholar"],
        },
    ]
    merged, conflicts = MODULE.merge_records(records)
    assert not conflicts
    registry = tmp_path / "registry.jsonl"
    MODULE.write_jsonl(registry, merged)
    output = tmp_path / "inspect.json"
    code = MODULE.command_inspect(
        SimpleNamespace(
            registry=registry,
            id=["10.1000/tagged"],
            max_abstract_chars=3000,
            output=output,
        )
    )
    card = json.loads(output.read_text())["papers"][0]
    assert code == 0
    assert card["nine_dimensional_tags"]["algorithm"] == [
        "algorithm.extragradient"
    ]
    assert card["profile_evidence"]["method"]["summary"].startswith("Use")


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


def test_audit_rejects_repeated_key_inside_one_citation_command(tmp_path) -> None:
    state = tmp_path / "state.json"
    state.write_text(json.dumps({"topic": "Example", "profile": "s2-only"}), encoding="utf-8")
    registry = tmp_path / "registry.jsonl"
    records = [
        {
            "title": f"Paper {index}",
            "authors": [f"Author {index}"],
            "year": 2020,
            "externalIds": {"ArXiv": f"2001.{index:05d}"},
            "bib_key": f"p{index}",
        }
        for index in range(105)
    ]
    MODULE.write_jsonl(registry, records)
    survey = tmp_path / "survey.tex"
    survey.write_text(
        "\\citep{p0,p0," + ",".join(f"p{i}" for i in range(1, 101)) + "}",
        encoding="utf-8",
    )
    related = tmp_path / "related.tex"
    related.write_text(
        "\\citep{" + ",".join(f"p{i}" for i in range(50)) + "}",
        encoding="utf-8",
    )
    bib = tmp_path / "references.bib"
    bib.write_text(
        "\n".join(f"@misc{{p{i}, title={{Paper {i}}}}}" for i in range(105)),
        encoding="utf-8",
    )
    output = tmp_path / "audit.json"

    code = MODULE.command_audit(
        SimpleNamespace(
            state=state,
            registry=registry,
            survey=survey,
            related=related,
            bib=bib,
            output=output,
        )
    )
    result = json.loads(output.read_text(encoding="utf-8"))

    assert code == 2
    assert result["gate_passed"] is False
    assert result["repeated_citation_key_count"] == 1
    assert result["gates"]["no_repeated_keys_within_citation"] is False


def test_named_attribution_audit_rejects_later_paper_as_original_source() -> None:
    records = [
        {
            "bib_key": "solodov2003",
            "title": "Convergence Rate Analysis of the Extragradient Method",
            "authors": ["Mikhail Solodov", "Paul Tseng"],
            "year": 2003,
        }
    ]
    tex = (
        "Korpelevich's extragradient construction founded the explicit correction "
        r"line \citep{solodov2003}."
    )

    issues = MODULE.named_attribution_issues(tex, records)

    assert len(issues) == 1
    assert issues[0]["claim_name"] == "Korpelevich"
    assert issues[0]["citation_keys"] == ["solodov2003"]


def test_named_attribution_audit_accepts_original_or_qualified_secondary_account() -> None:
    records = [
        {
            "bib_key": "korpelevich1976",
            "title": "The Extragradient Method",
            "authors": ["Galina M. Korpelevich"],
            "year": 1976,
        },
        {
            "bib_key": "solodov2003",
            "title": "Convergence Rate Analysis of the Extragradient Method",
            "authors": ["Mikhail Solodov", "Paul Tseng"],
            "year": 2003,
        },
    ]
    original = r"Korpelevich's method introduced the extra step \citep{korpelevich1976}."
    qualified = (
        "A later secondary account describes Korpelevich's method "
        r"\citep{solodov2003}."
    )

    assert MODULE.named_attribution_issues(original, records) == []
    assert MODULE.named_attribution_issues(qualified, records) == []


def test_named_attribution_audit_accepts_joint_named_result() -> None:
    records = [
        {
            "bib_key": "eckstein1992",
            "title": "Douglas--Rachford Splitting and the Proximal Point Algorithm",
            "authors": ["Jonathan Eckstein", "Dimitri P. Bertsekas"],
            "year": 1992,
        }
    ]
    tex = (
        "Eckstein--Bertsekas established the splitting connection "
        r"\citep{eckstein1992}."
    )

    assert MODULE.named_attribution_issues(tex, records) == []


def test_named_attribution_audit_does_not_treat_method_name_as_person() -> None:
    records = [
        {
            "bib_key": "juditsky2011",
            "title": "Solving Variational Inequalities with Stochastic Mirror-Prox",
            "authors": ["Anatoli Juditsky", "Arkadi Nemirovski"],
            "year": 2011,
        }
    ]
    tex = (
        "Stochastic Mirror-Prox established a standard baseline "
        r"\citep{juditsky2011}."
    )

    assert MODULE.named_attribution_issues(tex, records) == []


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


def test_bibtex_transliterates_latin_diacritics_for_t1_latex() -> None:
    escaped = MODULE.tex_escape("Jakovetić Karakuş Yıldırım Si‐cong")

    assert r"{\'c}" in escaped
    assert r"{\c s}" in escaped
    assert r"{\i}" in escaped
    assert "‐" not in escaped


def test_validate_doi_cli_accepts_cited_manuscripts() -> None:
    args = MODULE.parser().parse_args(
        [
            "validate-doi",
            "--registry", "registry.jsonl",
            "--cited-from", "survey.tex",
            "--cited-from", "related.tex",
            "--output-registry", "validated.jsonl",
            "--report", "report.json",
        ]
    )

    assert args.cited_from == [Path("survey.tex"), Path("related.tex")]


def test_metadata_enrichment_repairs_high_confidence_title_artifact(tmp_path, monkeypatch) -> None:
    registry = tmp_path / "registry.jsonl"
    MODULE.write_jsonl(
        registry,
        [{
            "title": "A Modified Forward-backward Splitting Method for Maximal Monotone Mappings 1",
            "authors": ["Paul Tseng"],
            "year": 1998,
            "bib_key": "tseng1998modified",
        }],
    )
    monkeypatch.setattr(
        MODULE,
        "fetch_crossref_candidates",
        lambda paper, rows, timeout: [{
            "DOI": "10.1137/S0363012998338806",
            "title": ["A Modified Forward-Backward Splitting Method for Maximal Monotone Mappings"],
            "author": [{"given": "Paul", "family": "Tseng"}],
            "issued": {"date-parts": [[2000]]},
            "container-title": ["SIAM Journal on Control and Optimization"],
            "volume": "38",
            "issue": "2",
            "page": "431-446",
        }],
    )
    output = tmp_path / "enriched.jsonl"
    report = tmp_path / "report.json"

    code = MODULE.command_enrich_metadata(
        SimpleNamespace(
            registry=registry,
            output_registry=output,
            report=report,
            cited_from=[],
            max_records=10,
            rows=5,
            min_title_similarity=0.82,
            min_author_overlap=0.5,
            max_year_delta=2,
            min_score_margin=0.05,
            timeout=1.0,
        )
    )

    record = MODULE.load_records(output)[0]
    assert code == 0
    assert record["title"].endswith("Maximal Monotone Mappings")
    assert MODULE.paper_doi(record) == "10.1137/s0363012998338806"
    assert record["publication_venue"] == "SIAM Journal on Control and Optimization"
    assert record["pages"] == "431-446"
    assert record["metadata_enrichment"]["status"] == "validated_crossref_title_author_year"


def test_metadata_enrichment_rejects_author_and_year_mismatch(tmp_path, monkeypatch) -> None:
    registry = tmp_path / "registry.jsonl"
    MODULE.write_jsonl(
        registry,
        [{"title": "A Reliable Method", "authors": ["Alice Author"], "year": 2020}],
    )
    monkeypatch.setattr(
        MODULE,
        "fetch_crossref_candidates",
        lambda paper, rows, timeout: [{
            "DOI": "10.1000/wrong",
            "title": ["A Reliable Method"],
            "author": [{"given": "Bob", "family": "Other"}],
            "issued": {"date-parts": [[2010]]},
        }],
    )
    output = tmp_path / "enriched.jsonl"
    report = tmp_path / "report.json"

    MODULE.command_enrich_metadata(
        SimpleNamespace(
            registry=registry,
            output_registry=output,
            report=report,
            cited_from=[],
            max_records=10,
            rows=5,
            min_title_similarity=0.82,
            min_author_overlap=0.5,
            max_year_delta=2,
            min_score_margin=0.05,
            timeout=1.0,
        )
    )

    assert MODULE.paper_doi(MODULE.load_records(output)[0]) == ""
    assert json.loads(report.read_text(encoding="utf-8"))["ambiguous_or_mismatch"] == 1


def test_default_survey_agent_has_no_worker_or_frozen_prompt_contract() -> None:
    agent = (ROOT / "agents/survey.toml").read_text(encoding="utf-8")

    assert "survey-outline" not in agent
    assert "survey-section-writer" not in agent
    assert "survey-related-works" not in agent
    assert "150000" not in agent
    assert "max-papers 140" not in agent
    normalized = " ".join(agent.casefold().split())
    assert "do not delegate" in normalized
    assert "do not follow a fixed staged workflow" in normalized
    assert "native web research remains" in normalized
    assert "do not precompute a candidate pool" in normalized
    assert len(agent.split()) < 450


def test_compact_survey_skill_keeps_metadata_as_postflight() -> None:
    skill = (
        ROOT / "skills/reasflow/survey/codex-first-survey/SKILL.md"
    ).read_text(encoding="utf-8")
    normalized = " ".join(skill.casefold().split())

    assert "native web search is the default" in normalized
    assert "do not construct a candidate pool or bibliography first" in normalized
    assert "works that the manuscript actually selects or cites" in normalized
