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


def test_reasflow_profiles_differ_only_by_reascholar_capability() -> None:
    assert MODULE.retrieval_profile("reasflow-s2") == "s2-only"
    assert MODULE.retrieval_profile("reasflow-reascholar") == "reascholar-s2"
