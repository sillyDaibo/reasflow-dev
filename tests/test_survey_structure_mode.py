from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace


SCRIPT = (
    Path(__file__).parents[1]
    / "skills/reasflow/survey/autosurvey-execution/scripts/autosurvey_tools.py"
)
SPEC = importlib.util.spec_from_file_location("autosurvey_tools_structure_test", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def _write_library(root: Path) -> Path:
    library = root / "survey" / "library" / "shared"
    library.mkdir(parents=True)
    papers = [
        {
            "id": "paper-a",
            "paper_key": "paper-a",
            "title": "Foundations of Distributed Optimization",
            "abstract": "A foundational consensus optimization method.",
            "abs": "A foundational consensus optimization method.",
            "year": 2020,
        },
        {
            "id": "paper-b",
            "paper_key": "paper-b",
            "title": "Gradient Tracking for Distributed Optimization",
            "abstract": "A later gradient-tracking method.",
            "abs": "A later gradient-tracking method.",
            "year": 2021,
        },
    ]
    (library / "paper_pool.jsonl").write_text(
        "".join(json.dumps(paper) + "\n" for paper in papers), encoding="utf-8"
    )
    pack = {
        "schema_version": "reascholar-structure-pack-v1",
        "role": "provisional_structure",
        "domains": [
            {
                "domain_id": 1,
                "title": "Distributed Optimization over Networks",
                "description": "Consensus and gradient-tracking branches.",
            }
        ],
        "timeline": [
            {
                "candidate_claim": "Consensus methods preceded gradient tracking.",
                "period_start": 2020,
                "period_end": 2021,
                "support_papers": [
                    {"paper_key": "paper-a", "title": papers[0]["title"]},
                    {"paper_key": "paper-b", "title": papers[1]["title"]},
                ],
            }
        ],
        "gaps": [],
        "future_work": [],
        "citation_relations": [
            {
                "citing_title": papers[1]["title"],
                "cited_title": papers[0]["title"],
            }
        ],
        "warnings": [],
    }
    (library / "structure_pack.json").write_text(json.dumps(pack), encoding="utf-8")
    return library


def _native_args(root: Path, mode: str, output_name: str) -> SimpleNamespace:
    return SimpleNamespace(
        workspace=str(root),
        db_path="",
        embedding_model="",
        library_dir="survey/library/shared",
        structure_mode=mode,
        structure_pack="",
        topic="distributed optimization",
        outline_path="survey/outline.md",
        output_path=f"survey/{output_name}",
        rag_num=10,
        max_papers=10,
        max_external_papers=10,
        min_words=1000,
        target_words=1500,
        frozen_pool_only=True,
    )


def test_include_and_exclude_share_identical_frozen_library(tmp_path: Path) -> None:
    _write_library(tmp_path)
    (tmp_path / "survey" / "outline.md").write_text(
        "# Distributed Optimization\n"
        "## Foundations\n"
        "### Consensus\n"
        "Description: consensus optimization foundations\n"
        "## Gradient Tracking\n"
        "### Evolution\n"
        "Description: gradient tracking evolution\n",
        encoding="utf-8",
    )

    MODULE._DB_INSTANCE = None
    assert (
        MODULE.command_prepare_native_survey_data(
            _native_args(tmp_path, "include", "include.json")
        )
        == 0
    )
    MODULE._DB_INSTANCE = None
    assert (
        MODULE.command_prepare_native_survey_data(
            _native_args(tmp_path, "exclude", "exclude.json")
        )
        == 0
    )

    included = json.loads((tmp_path / "survey" / "include.json").read_text())
    excluded = json.loads((tmp_path / "survey" / "exclude.json").read_text())
    assert included["paper_count"] == excluded["paper_count"]
    assert included["paper_ids"] == excluded["paper_ids"]
    assert included["frozen_pool_only"] is True
    assert excluded["frozen_pool_only"] is True
    assert included["external_paper_count"] == excluded["external_paper_count"]
    assert included["paper_library"] == excluded["paper_library"]
    assert included["paper_library"]["paper_pool_line_count"] == 2
    assert included["structure"]["included"] is True
    assert excluded["structure"]["included"] is False
    assert "ReaScholar structure treatment" in included["prompt"]
    assert "ReaScholar structure treatment" not in excluded["prompt"]
    assert "without mentioning ReaScholar" in included["prompt"]
    assert "Foundations of Distributed Optimization" in included["prompt"]
    assert "Foundations of Distributed Optimization" in excluded["prompt"]
    assert "complete, independently compilable academic survey in LaTeX" in included["prompt"]
    assert "\\documentclass" in included["prompt"]
    assert "paper_citation_key:" in included["prompt"]
    assert included["min_unique_citations"] == 100
    assert included["target_unique_citations"] == 110
    assert (tmp_path / "survey" / "references.bib").is_file()
    metadata = json.loads((tmp_path / "survey" / "survey.json").read_text())
    assert metadata["schema_version"] == "tex-survey-v1"
    assert len(metadata["citation_key_map"]) == 2


def test_include_requires_a_nonempty_structure_pack(tmp_path: Path) -> None:
    library = tmp_path / "survey" / "library" / "shared"
    library.mkdir(parents=True)
    args = SimpleNamespace(
        library_dir="survey/library/shared",
        structure_mode="include",
        structure_pack="",
    )
    try:
        MODULE.load_structure_context(tmp_path, args)
    except FileNotFoundError as exc:
        assert "required but missing" in str(exc)
    else:
        raise AssertionError("include mode silently accepted a missing structure pack")


def test_outline_uses_bounded_deterministic_evidence_manifest(tmp_path: Path) -> None:
    _write_library(tmp_path)
    args = SimpleNamespace(
        workspace=str(tmp_path),
        db_path="",
        embedding_model="",
        library_dir="survey/library/shared",
        structure_mode="exclude",
        structure_pack="",
        topic="distributed optimization",
        output_path="survey/stage1.json",
        section_num=7,
        reference_num=1,
        rag_num=60,
        chunk_size=30000,
        task_path="",
        max_abstract_chars=12,
        frozen_pool_only=False,
    )

    assert MODULE.command_prepare_outline_data(args) == 0
    output = json.loads((tmp_path / "survey" / "stage1.json").read_text())
    assert output["frozen_pool_only"] is True
    assert output["max_abstract_chars"] == 12
    assert output["evidence_selection"]["selected_count"] == 1
    assert output["evidence_selection"]["max_papers"] == 1
    assert len(output["prompts"]) == 1
    assert "A foundational consensus optimization method." not in output["prompts"][0]["prompt"]


def test_internal_reascholar_id_is_not_rendered_as_arxiv_eprint() -> None:
    paper = {
        "id": "reascholar:820_internal_10.1007%2Fexample",
        "title": "Published optimization paper",
        "authors": ["A. Author"],
        "year": 2022,
        "externalIds": {"DOI": "10.1007/example"},
        "doi": "10.1007/example",
    }

    assert MODULE._paper_arxiv_id(paper) == ""
    bibtex = MODULE.arxiv_id_to_bibtex(paper, "author2022published")
    assert "eprint" not in bibtex.lower()
    assert "archiveprefix" not in bibtex.lower()
    assert "reascholar:" not in bibtex


def test_real_arxiv_id_is_preserved_in_fallback_bibtex() -> None:
    paper = {
        "id": "s2:example",
        "title": "Preprint paper",
        "authors": ["A. Author"],
        "year": 2025,
        "externalIds": {"ArXiv": "2501.01234v2"},
    }

    assert MODULE._paper_arxiv_id(paper) == "2501.01234v2"
    bibtex = MODULE.arxiv_id_to_bibtex(paper, "author2025preprint")
    assert bibtex.startswith("@misc{")
    assert "eprint = {2501.01234v2}" in bibtex
    assert "archiveprefix = {arXiv}" in bibtex


def test_published_conference_bibtex_uses_booktitle_and_suppresses_url() -> None:
    paper = {
        "title": "Communication-Efficient SGD with ADMM",
        "authors": ["A. Author", "B. Author"],
        "year": 2024,
        "publication_venue": "Proceedings of the Example Conference",
        "publication_types": ["Conference"],
        "pages": "101--112",
        "publisher": "Example Press",
        "externalIds": {
            "DOI": "10.1000/example",
            "ArXiv": "2401.01234",
        },
    }

    bibtex = MODULE.arxiv_id_to_bibtex(paper, "author2024communication")

    assert bibtex.startswith("@inproceedings{")
    assert "booktitle = {Proceedings of the Example Conference}" in bibtex
    assert "pages = {101--112}" in bibtex
    assert "publisher = {Example Press}" in bibtex
    assert "doi = {10.1000/example}" in bibtex
    assert "url =" not in bibtex
    assert "eprint =" not in bibtex
    assert "{SGD}" in bibtex
    assert "{ADMM}" in bibtex


def test_published_journal_bibtex_has_volume_issue_pages_without_url() -> None:
    paper = {
        "title": "A Journal Result for Distributed Optimization",
        "authors": ["A. Author"],
        "year": 2023,
        "publication_venue": "Journal of Example Results",
        "publication_types": ["JournalArticle"],
        "journal": {
            "name": "Journal of Example Results",
            "volume": "12",
            "pages": "44--63",
        },
        "issue": "3",
        "externalIds": {"DOI": "10.1000/journal"},
    }

    bibtex = MODULE.arxiv_id_to_bibtex(paper, "author2023journal")

    assert bibtex.startswith("@article{")
    assert "journal = {Journal of Example Results}" in bibtex
    assert "volume = {12}" in bibtex
    assert "number = {3}" in bibtex
    assert "pages = {44--63}" in bibtex
    assert "doi = {10.1000/journal}" in bibtex
    assert "url =" not in bibtex


def test_mixed_formal_venue_and_arxiv_volume_becomes_explicit_preprint() -> None:
    paper = {
        "title": "An Error Feedback Result",
        "authors": ["A. Author"],
        "year": 2024,
        "externalIds": {"ArXiv": "2401.01234", "DOI": "10.48550/arXiv.2401.01234"},
    }
    mixed = """@article{author2024result,
  title = {An Error Feedback Result},
  author = {A. Author},
  journal = {Example Conference},
  volume = {abs/2401.01234},
  year = {2024},
  url = {https://doi.org/10.48550/arXiv.2401.01234}
}"""

    bibtex = MODULE.enrich_bibtex_entry(paper, mixed)

    assert bibtex.startswith("@misc{")
    assert "journal =" not in bibtex
    assert "volume =" not in bibtex
    assert "doi =" not in bibtex
    assert "eprint = {2401.01234}" in bibtex
    assert "archiveprefix = {arXiv}" in bibtex
    assert "url = {https://arxiv.org/abs/2401.01234}" in bibtex


def test_formal_doi_discards_stale_arxiv_volume_and_url() -> None:
    paper = {
        "title": "A Published Result",
        "authors": ["A. Author"],
        "year": 2022,
        "externalIds": {"ArXiv": "2101.01234", "DOI": "10.1000/published"},
    }
    mixed = """@article{author2022result,
  title = {A Published Result},
  author = {A. Author},
  journal = {Journal of Results},
  volume = {abs/2101.01234},
  year = {2021},
  doi = {10.1000/published},
  url = {https://arxiv.org/abs/2101.01234}
}"""

    bibtex = MODULE.enrich_bibtex_entry(paper, mixed)

    assert bibtex.startswith("@article{")
    assert "journal = {Journal of Results}" in bibtex
    assert "volume =" not in bibtex
    assert "doi = {10.1000/published}" in bibtex
    assert "url =" not in bibtex


def test_reference_key_map_prefers_assigned_human_readable_key() -> None:
    references = {"1": "paper-1"}
    papers = {
        "paper-1": {
            "title": "A Result",
            "authors": ["A. Author"],
            "year": 2024,
            "bib_key": "author2024result",
            "raw_bibtex": "@article{reascholar_deadbeef, title={A Result}}",
        }
    }

    key_map = MODULE.normalize_reference_key_map(references, papers)

    assert key_map == {"1": "author2024result"}
    rendered = MODULE.render_bibtex(references, papers, key_map)
    assert rendered.startswith("@article{author2024result,")
    assert "reascholar_deadbeef" not in rendered


def test_compact_tex_is_not_rejected_by_physical_line_count(tmp_path: Path) -> None:
    survey = tmp_path / "survey"
    related = tmp_path / "related_works"
    survey.mkdir()
    related.mkdir()
    (survey / "survey.tex").write_text(
        "\\documentclass{article}\\begin{document}"
        "\\subsection{Overview} Compact evidence \\citep{paper}."
        "\\end{document}\n",
        encoding="utf-8",
    )
    (survey / "survey.json").write_text("{}\n", encoding="utf-8")
    (survey / "references.bib").write_text(
        "@article{paper,title={A Paper},year={2024}}\n", encoding="utf-8"
    )
    (related / "related_works.tex").write_text(
        "\\subsection{Prior Work} Evidence \\citep{paper}.\n", encoding="utf-8"
    )

    report = MODULE.ensure_final_survey_package(
        tmp_path,
        "survey",
        "related_works",
        "test topic",
        min_survey_words=1,
        min_survey_subsections=1,
        min_related_citations=1,
        max_related_citations=1,
        min_related_words=1,
        min_related_sections=1,
        min_survey_citations=1,
    )

    assert report["survey_lines"] < 450
    assert report["quality"]["survey_min_lines"] == 0
    assert report["quality"]["survey_lines_ok"] is True
    assert report["quality"]["ok"] is True


def test_tex_word_count_matches_normalized_benchmark_contract() -> None:
    tex = r"""
\documentclass[11pt]{article}
\usepackage{amsmath}
\begin{document}
\section{A Useful Heading}
Rendered prose has five words \citep{very_long_fake_citation_key}.
\end{document}
"""

    assert MODULE.count_tex_content_words(tex) == 13


def test_final_reference_maps_merge_transitive_cross_source_duplicates() -> None:
    reference_ids = {"1": "first", "2": "second", "3": "third"}
    references_full = {
        "first": {
            "title": "Canonical Optimization Result",
            "externalIds": {"DOI": "10.1000/result", "ArXiv": "2401.12345"},
        },
        "second": {
            "title": "Canonical Optimization Result",
            "externalIds": {"ArXiv": "2401.12345v2"},
        },
        "third": {
            "title": "Canonical Optimization Result",
            "doi": "https://doi.org/10.1000/result",
        },
    }

    canonical_ids, canonical_full, aliases, report = MODULE.canonicalize_reference_maps(
        reference_ids, references_full
    )

    assert canonical_ids == {"1": "first"}
    assert list(canonical_full) == ["first"]
    assert aliases == {"2": "1", "3": "1"}
    assert report["merged_reference_count"] == 2
    assert report["duplicate_canonical_identity_count"] == 0
    assert report["gate_passed"] is True
    assert MODULE.rewrite_numeric_reference_aliases(
        "Evidence [1, 2] and confirmation [3].", aliases
    ) == "Evidence [1] and confirmation [1]."


def test_balanced_evidence_selector_pins_anchors_and_deprioritizes_empty_records() -> None:
    papers = []
    for index in range(10):
        papers.append(
            {
                "id": f"complete-{index}",
                "title": f"Gradient Tracking Evidence {index}",
                "abstract": (
                    "Gradient tracking compares network assumptions, convergence "
                    "guarantees, communication, and stochastic limitations. " * 4
                ),
                "citationCount": 20 + index,
            }
        )
    papers.extend(
        {
            "id": f"empty-{index}",
            "title": f"Sparse Metadata Record {index}",
            "abstract": "",
            "citationCount": 10000,
        }
        for index in range(30)
    )
    anchor_title = "Required Exact Correction Anchor"
    papers.append({"id": "anchor", "title": anchor_title, "abstract": ""})
    parsed = {
        "sections": ["Foundations", "Gradient Tracking"],
        "section_descriptions": ["consensus", "network gradient estimation"],
        "subsections": [["Consensus"], ["Convergence"]],
        "subsection_descriptions": [
            ["mixing assumptions"],
            ["rates and limitations"],
        ],
    }

    selected, manifest = MODULE.select_native_evidence(
        papers,
        "distributed optimization",
        parsed,
        max_papers=12,
        required_references=[{"title": anchor_title}],
    )

    assert len(selected) == 12
    assert anchor_title in {paper["title"] for paper in selected}
    assert manifest["pinned_anchor_count"] == 1
    assert manifest["selected_with_abstract_ge_100"] == 10
    assert manifest["selected_empty_abstract"] == 2
    assert manifest["policy"] == "deterministic-balanced-topic-gated-evidence-v2"
    assert manifest["topic_irrelevant_candidate_count"] == 0
    assert manifest["selected_ids_sha256"]


def test_native_evidence_excludes_informative_but_off_topic_papers() -> None:
    papers = [
        {
            "id": "relevant",
            "title": "Quantized Communication for Distributed Optimization",
            "abstract": "Compression and quantization reduce communication cost.",
        },
        {
            "id": "off-topic",
            "title": "Arithmetic Optimization Algorithm",
            "abstract": "A well documented population-based optimization method. " * 20,
            "citationCount": 10000,
        },
    ]

    selected, manifest = MODULE.select_native_evidence(
        papers,
        "quantized communication in distributed optimization",
        {"sections": [], "subsections": []},
        max_papers=10,
    )

    assert [paper["id"] for paper in selected] == ["relevant"]
    assert manifest["topic_relevant_candidate_count"] == 1
    assert manifest["topic_irrelevant_candidate_count"] == 1


def test_writer_evidence_rendering_has_an_aggregate_character_budget() -> None:
    papers = [
        {
            "title": f"Evidence Paper {index}",
            "abstract": "abstract evidence " * 1000,
            "strengths": "strength " * 1000,
            "weaknesses": "weakness " * 1000,
        }
        for index in range(120)
    ]
    rendered = MODULE._format_papers_text_bounded(papers, 150000)

    assert len(rendered) <= 152000
    assert rendered.count("paper_title:") == 120
    assert "Evidence Paper 0" in rendered
    assert "Evidence Paper 119" in rendered


def test_related_works_handoff_preserves_late_gap_relations(tmp_path: Path) -> None:
    long_prefix = (
        "## Foundations\n\nA concrete mechanism improves convergence [1].\n\n"
        + ("Foundational context remains relevant. " * 220)
    )
    late_gap = (
        "However, this limitation is counterevidence to the broad guarantee, and "
        "the residual gap remains an open problem for future work [2]."
    )
    survey_data = {
        "survey": long_prefix + "\n\n## Open Problems\n\n" + late_gap + "\n\n## References\n\n[1] Alpha\n[2] Beta",
        "reference": {"1": "alpha", "2": "beta"},
        "reference_full": {
            "alpha": {
                "title": "Alpha Method",
                "authors": ["A. Author"],
                "year": 2020,
                "abs": "A mechanism paper.",
            },
            "beta": {
                "title": "Beta Limitation",
                "authors": ["B. Author"],
                "year": 2021,
                "abs": "A limitation paper.",
            },
        },
    }
    (tmp_path / "survey").mkdir()
    (tmp_path / "survey" / "survey.json").write_text(
        json.dumps(survey_data), encoding="utf-8"
    )
    args = SimpleNamespace(
        workspace=str(tmp_path),
        topic="distributed optimization",
        survey_path="survey/survey.json",
        output_path="related_works/rw_prompt.json",
        min_citations=1,
        target_citations=2,
        min_words=700,
        max_words=1000,
        survey_context_chars=60000,
    )

    assert MODULE.command_prepare_related_works_data(args) == 0
    output = json.loads(
        (tmp_path / "related_works" / "rw_prompt.json").read_text(encoding="utf-8")
    )
    assert late_gap in output["prompt"]
    assert "residual gap" in output["relation_brief"]
    assert "aim to use every mapped citation key" not in output["prompt"]
    assert "Do not try to cite every mapped key" in output["prompt"]
    assert "## References" not in output["prompt"]
