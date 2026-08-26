from __future__ import annotations

import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).parents[1]
SCRIPT = ROOT / "scripts/run_codex_first_ablation.py"
SPEC = importlib.util.spec_from_file_location("run_codex_first_ablation", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def public_task() -> dict:
    return {
        "task_visibility_contract": "generation-public-v1",
        "task_id": "ontology3k_example",
        "topic": "Example Optimization Topic",
        "cutoff_date": "2026-07-31",
        "expected_aspects": [{"name": "Foundations"}, {"name": "Methods"}],
    }


def test_public_task_rejects_evaluator_only_fields(tmp_path) -> None:
    task = public_task()
    task["future_work_expectations"] = ["hidden"]
    try:
        MODULE.require_public_task(task, tmp_path / "task.yaml")
    except ValueError as exc:
        assert "future_work_expectations" in str(exc)
    else:
        raise AssertionError("hidden evaluator field was accepted")


def test_three_arms_share_exact_prompt_and_task_projection(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(MODULE, "install_reasflow", lambda workspace, source: (workspace / ".codex").mkdir(parents=True))
    monkeypatch.setattr(MODULE, "direct_survey_config", lambda source: "developer_instructions='direct'\n")
    monkeypatch.setattr(MODULE.subprocess, "check_output", lambda *args, **kwargs: "deadbeef\n")
    task = public_task()
    prompts = []
    task_views = []
    hashes = []
    for arm in MODULE.ARMS:
        workspace = tmp_path / arm
        MODULE.prepare_arm(workspace, arm, task, ROOT)
        prompts.append((workspace / "prompt.txt").read_text(encoding="utf-8"))
        task_views.append((workspace / "TASK.md").read_text(encoding="utf-8"))
        hashes.append(json.loads((workspace / "run_manifest.json").read_text())["prompt_sha256"])

    assert len(set(prompts)) == 1
    assert len(set(task_views)) == 1
    assert len(set(hashes)) == 1
    assert "citation format" not in prompts[0].casefold()
    assert "cite more than 100" in prompts[0].casefold()
    assert "1,200--2,200 words" in prompts[0]
    assert "45--55 core papers" in prompts[0]
    assert "at least four titled sections" in prompts[0]
    assert "each canonical paper has only one" in prompts[0]


def test_reasflow_profiles_differ_only_by_reascholar_capability() -> None:
    assert MODULE.retrieval_profile("reasflow-s2") == "s2-only"
    assert MODULE.retrieval_profile("reasflow-reascholar") == "reascholar-s2"


def test_package_deliverables_names_topic_arm_and_author(tmp_path) -> None:
    survey = tmp_path / "survey/survey.pdf"
    related = tmp_path / "related_works/related_works.pdf"
    survey.parent.mkdir()
    related.parent.mkdir()
    survey.write_bytes(b"survey")
    related.write_bytes(b"related")

    outputs = MODULE.package_deliverables(
        tmp_path, "error_feedback", "reasflow-reascholar"
    )

    assert outputs == [
        "error_feedback__survey__reasflow-reascholar__ReasFlow-ReaScholar.pdf",
        "error_feedback__related-works__reasflow-reascholar__ReasFlow-ReaScholar.pdf",
    ]
    assert (tmp_path / outputs[0]).read_bytes() == b"survey"
    assert (tmp_path / outputs[1]).read_bytes() == b"related"


def test_publication_tool_path_finds_shared_workspace_toolchain(tmp_path) -> None:
    toolchain = tmp_path / ".toolchain/survey-pdf"
    toolchain.mkdir(parents=True)
    (toolchain / "tectonic").write_bytes(b"binary")
    workspace = tmp_path / "runs/experiment/task/arm"
    workspace.mkdir(parents=True)

    assert MODULE.publication_tool_path(workspace) == toolchain


def test_canonicalize_root_level_publication_without_rewriting_content(tmp_path) -> None:
    (tmp_path / "survey.tex").write_text("survey source", encoding="utf-8")
    (tmp_path / "survey.pdf").write_bytes(b"survey pdf")
    (tmp_path / "related_works.tex").write_text("related source", encoding="utf-8")
    (tmp_path / "related_works.pdf").write_bytes(b"related pdf")
    (tmp_path / "references.bib").write_text("bibliography", encoding="utf-8")
    (tmp_path / "survey.txt").write_text("stale rendered text", encoding="utf-8")
    (tmp_path / "related_works.md").write_text("stale markdown", encoding="utf-8")
    sections = tmp_path / "sections"
    sections.mkdir()
    (sections / "body.tex").write_text("section", encoding="utf-8")

    MODULE.canonicalize_publication_layout(tmp_path)

    assert (tmp_path / "survey/survey.tex").read_text() == "survey source"
    assert (tmp_path / "survey/survey.pdf").read_bytes() == b"survey pdf"
    assert (tmp_path / "survey/references.bib").read_text() == "bibliography"
    assert (tmp_path / "survey/sections/body.tex").read_text() == "section"
    assert (tmp_path / "related_works/related_works.tex").read_text() == "related source"
    assert not (tmp_path / "survey.txt").exists()
    assert not (tmp_path / "related_works.md").exists()


def test_publication_validation_reports_mechanical_deficits(tmp_path) -> None:
    survey = tmp_path / "survey"
    related = tmp_path / "related_works"
    survey.mkdir()
    related.mkdir()
    (survey / "survey.tex").write_text(
        "A short survey " + r"\cite{one,two}", encoding="utf-8"
    )
    (related / "related_works.tex").write_text(
        "Short related work " + r"\cite{one}", encoding="utf-8"
    )

    result = MODULE.publication_validation(tmp_path)

    assert result["ok"] is False
    assert result["survey"]["distinct_citations"] == 2
    assert result["related_works"]["distinct_citations"] == 1
    assert result["checks"]["survey_words"] is False
    assert result["checks"]["related_words"] is False
    assert result["checks"]["related_sections"] is False
    assert result["checks"]["build_report"] is False


def test_tex_metrics_expands_local_input_files(tmp_path) -> None:
    sections = tmp_path / "sections"
    sections.mkdir()
    (tmp_path / "survey.tex").write_text(
        r"Opening \cite{one}\input{sections/body}", encoding="utf-8"
    )
    (sections / "body.tex").write_text(
        r"Included prose \cite{two,three}", encoding="utf-8"
    )

    metrics = MODULE.tex_metrics(tmp_path / "survey.tex")

    assert metrics["distinct_citations"] == 3
    assert metrics["word_count"] == 3
    assert metrics["section_count"] == 0


def test_repair_prompt_discloses_only_shared_mechanical_requirements() -> None:
    validation = {
        "survey": {"word_count": 2600, "distinct_citations": 86},
        "related_works": {
            "word_count": 945,
            "distinct_citations": 57,
            "section_count": 1,
        },
    }

    prompt = MODULE.repair_prompt(validation)

    assert "Survey words=2600" in prompt
    assert "Related Works distinct citations=57" in prompt
    assert "10,000 substantive words" in prompt
    assert "45--55 core papers" in prompt
    assert "Related Works titled sections=1" in prompt
    assert "each canonical paper has one" in prompt
    assert "key reference" not in prompt.casefold()
