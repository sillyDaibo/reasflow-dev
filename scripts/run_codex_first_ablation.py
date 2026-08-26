#!/usr/bin/env python3
"""Prepare or run fair Pure Codex / ReasFlow / ReaScholar survey arms."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

import yaml


ARMS = ("pure-codex", "reasflow-s2", "reasflow-reascholar")
FORBIDDEN_TASK_FIELDS = {
    "key_references", "gap_requirements", "future_work_expectations", "logic_chain"
}
COMMON_PROMPT = """Read `TASK.md` and `AUTHOR_LABEL.txt` in the current workspace. Write a rigorous, self-contained survey article on the specified topic for expert review. Explain the problem setting to a new researcher, organize the literature into a useful taxonomy, describe the research development, compare representative approaches and their tradeoffs, and identify well-supported limitations, open questions, and future directions. The main survey body must contain at least 10,000 words and should naturally develop to roughly 12,000 words when the evidence supports it. Cite more than 100 distinct papers that are substantively relevant to the topic; do not target a round number and do not satisfy the coverage requirement with peripheral or merely keyword-matching references. The focused Related Works article must contain 1,200--2,200 words and use 45--55 core papers. Use the research resources and tools available in the workspace. Work autonomously and deliver complete LaTeX sources, one bibliography, and compiled PDFs, with the author shown exactly as specified in `AUTHOR_LABEL.txt`."""
MIN_SURVEY_WORDS = 10_000
MIN_SURVEY_CITATIONS = 101
MIN_RELATED_WORDS = 1_200
MAX_RELATED_WORDS = 2_200
MIN_RELATED_CITATIONS = 45
MAX_RELATED_CITATIONS = 55


def require_public_task(task: dict[str, Any], path: Path) -> None:
    contract = task.get("task_visibility_contract")
    forbidden = sorted(FORBIDDEN_TASK_FIELDS & set(task))
    aspect_keywords = any(
        isinstance(item, dict) and item.get("keywords")
        for item in task.get("expected_aspects", [])
    )
    if contract != "generation-public-v1" or forbidden or aspect_keywords:
        raise ValueError(
            f"{path} is not generation-public-v1: forbidden={forbidden}, "
            f"aspect_keywords={aspect_keywords}"
        )


def task_slug(task: dict[str, Any], path: Path) -> str:
    value = str(task.get("task_id") or path.stem)
    if value.startswith("ontology3k_"):
        value = value.removeprefix("ontology3k_")
    slug = "".join(char if char.isalnum() or char in "-_" else "_" for char in value)
    if not slug:
        raise ValueError(f"cannot derive task slug from {path}")
    return slug


def render_task(task: dict[str, Any]) -> str:
    aspects = []
    for item in task.get("expected_aspects", []):
        aspects.append(str(item.get("name")) if isinstance(item, dict) else str(item))
    lines = [
        f"Topic: {task['topic']}",
        f"Literature cutoff: {task.get('cutoff_date', '2026-07-31')}",
        "Expected aspects:",
    ]
    lines.extend(f"- {item}" for item in aspects)
    return "\n".join(lines) + "\n"


def author_label(arm: str) -> str:
    return {
        "pure-codex": "Codex--WebSearch",
        "reasflow-s2": "ReasFlow--CodexFirst",
        "reasflow-reascholar": "ReasFlow--ReaScholar",
    }[arm]


def retrieval_profile(arm: str) -> str:
    return {
        "pure-codex": "native-web-only",
        "reasflow-s2": "s2-only",
        "reasflow-reascholar": "reascholar-s2",
    }[arm]


def filename_token(value: str) -> str:
    token = re.sub(r"[^A-Za-z0-9_-]+", "-", value).strip("-")
    token = re.sub(r"-+", "-", token)
    return token or "unknown"


def package_deliverables(workspace: Path, slug: str, arm: str) -> list[str]:
    label = filename_token(author_label(arm))
    outputs = []
    for source, kind in (
        (workspace / "survey/survey.pdf", "survey"),
        (workspace / "related_works/related_works.pdf", "related-works"),
    ):
        if not source.is_file():
            continue
        destination = workspace / f"{slug}__{kind}__{arm}__{label}.pdf"
        shutil.copy2(source, destination)
        outputs.append(destination.name)
    return outputs


def publication_tool_path(workspace: Path) -> Path | None:
    for parent in (workspace, *workspace.parents):
        candidate = parent / ".toolchain/survey-pdf"
        if (candidate / "tectonic").is_file():
            return candidate
    return None


def canonicalize_publication_layout(workspace: Path) -> None:
    """Adapt root-level TeX delivery without changing manuscript content."""
    for stem, directory in (("survey", "survey"), ("related_works", "related_works")):
        source_tex = workspace / f"{stem}.tex"
        source_pdf = workspace / f"{stem}.pdf"
        if not source_tex.is_file():
            continue
        destination = workspace / directory
        destination.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_tex, destination / f"{stem}.tex")
        if source_pdf.is_file():
            shutil.copy2(source_pdf, destination / f"{stem}.pdf")
        bibliography = workspace / "references.bib"
        if bibliography.is_file():
            shutil.copy2(bibliography, destination / "references.bib")
        sections = workspace / "sections"
        if sections.is_dir():
            shutil.copytree(sections, destination / "sections", dirs_exist_ok=True)


def read_tex_tree(path: Path, root: Path, seen: set[Path] | None = None) -> str:
    resolved = path.resolve()
    root = root.resolve()
    visited = seen if seen is not None else set()
    if not resolved.is_file() or not resolved.is_relative_to(root) or resolved in visited:
        return ""
    visited.add(resolved)
    text = resolved.read_text(encoding="utf-8", errors="ignore")

    def include(match: re.Match[str]) -> str:
        relative = Path(match.group(1))
        if not relative.suffix:
            relative = relative.with_suffix(".tex")
        return read_tex_tree(resolved.parent / relative, root, visited)

    return re.sub(r"\\(?:input|include)\{([^}]+)\}", include, text)


def tex_metrics(path: Path) -> dict[str, int]:
    text = read_tex_tree(path, path.parent)
    if not text:
        return {"word_count": 0, "distinct_citations": 0}
    text = re.sub(r"(?m)%.*$", " ", text)
    citation_keys = {
        key.strip()
        for match in re.finditer(r"\\cite\w*\{([^}]*)\}", text)
        for key in match.group(1).split(",")
        if key.strip()
    }
    prose = re.sub(r"\\cite\w*\{[^}]*\}", " ", text)
    prose = re.sub(r"\\(?:begin|end)\{[^}]+\}", " ", prose)
    prose = re.sub(r"\\[A-Za-z@]+\*?(?:\[[^]]*\])?", " ", prose)
    prose = re.sub(r"[^A-Za-z0-9'-]+", " ", prose)
    words = re.findall(r"\b[A-Za-z][A-Za-z0-9'-]*\b", prose)
    return {"word_count": len(words), "distinct_citations": len(citation_keys)}


def publication_validation(workspace: Path) -> dict[str, Any]:
    survey = tex_metrics(workspace / "survey/survey.tex")
    related = tex_metrics(workspace / "related_works/related_works.tex")
    checks = {
        "survey_words": survey["word_count"] >= MIN_SURVEY_WORDS,
        "survey_citations": survey["distinct_citations"] >= MIN_SURVEY_CITATIONS,
        "related_words": MIN_RELATED_WORDS <= related["word_count"] <= MAX_RELATED_WORDS,
        "related_citations": (
            MIN_RELATED_CITATIONS
            <= related["distinct_citations"]
            <= MAX_RELATED_CITATIONS
        ),
        "survey_pdf": (workspace / "survey/survey.pdf").is_file(),
        "related_pdf": (workspace / "related_works/related_works.pdf").is_file(),
    }
    return {
        "ok": all(checks.values()),
        "survey": survey,
        "related_works": related,
        "checks": checks,
    }


def repair_prompt(validation: dict[str, Any]) -> str:
    survey = validation["survey"]
    related = validation["related_works"]
    return f"""Continue the existing survey publication and repair only its measured delivery deficits. This is the same mechanical feedback protocol used for every experimental arm. Preserve correct content, topic scope, author label, and source provenance; do not pad with peripheral citations. The completed main Survey must contain at least {MIN_SURVEY_WORDS:,} substantive words and more than 100 distinct relevant citations. The Related Works article must contain {MIN_RELATED_WORDS:,}--{MAX_RELATED_WORDS:,} substantive words and cite {MIN_RELATED_CITATIONS}--{MAX_RELATED_CITATIONS} core papers. The current mechanical scan found Survey words={survey['word_count']}, Survey distinct citations={survey['distinct_citations']}, Related Works words={related['word_count']}, and Related Works distinct citations={related['distinct_citations']}. Correct every failing requirement, retain complete LaTeX and one bibliography, recompile both PDFs, and verify the final counts before finishing."""


def write_publication_validation(workspace: Path) -> dict[str, Any]:
    result = publication_validation(workspace)
    (workspace / "publication_validation.json").write_text(
        json.dumps(result, indent=2) + "\n", encoding="utf-8"
    )
    return result


def install_reasflow(workspace: Path, source: Path) -> None:
    env = dict(os.environ)
    env["REASFLOW_DEV_SOURCE_DIR"] = str(source)
    subprocess.run(
        [str(source / "install.sh"), "--local", "--force"],
        cwd=workspace,
        env=env,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )


def direct_survey_config(source: Path) -> str:
    agent_text = (source / "agents/survey.toml").read_text(encoding="utf-8")
    match = re.search(r"developer_instructions\s*=\s*'''(.*?)'''", agent_text, re.DOTALL)
    if not match:
        raise ValueError("survey.toml has no literal developer_instructions block")
    instructions = match.group(1).strip()
    instructions += """

Before acting, read these installed skills completely and follow their routing:
- `.codex/reasflow-skills/survey/codex-first-survey/SKILL.md`
- `.codex/reasflow-skills/survey/autosurvey-paper-retrieval/SKILL.md`
- `.codex/reasflow-skills/survey/reascholar-two-stage-retrieval/SKILL.md`
- `.codex/reasflow-skills/survey/survey-tex-bib-packaging/SKILL.md`
This is a direct single-agent survey run. Do not spawn another survey agent.
"""
    return "developer_instructions = '''\n" + instructions + "\n'''\n"


def prepare_arm(workspace: Path, arm: str, task: dict[str, Any], source: Path) -> None:
    workspace.mkdir(parents=True, exist_ok=True)
    (workspace / "TASK.md").write_text(render_task(task), encoding="utf-8")
    (workspace / "AUTHOR_LABEL.txt").write_text(author_label(arm) + "\n", encoding="utf-8")
    (workspace / "prompt.txt").write_text(COMMON_PROMPT + "\n", encoding="utf-8")
    if arm == "pure-codex":
        (workspace / "AGENTS.md").write_text(
            "# Pure Codex baseline\n\n"
            "Use the shared task prompt and public web sources. Do not read or call "
            "ReasFlow, ReaScholar, Semantic Scholar helper scripts, local paper "
            "databases, or manuscripts from other workspaces. Do not spawn subagents.\n",
            encoding="utf-8",
        )
    else:
        install_reasflow(workspace, source)
        (workspace / ".codex/config.toml").write_text(
            direct_survey_config(source), encoding="utf-8"
        )
    manifest = {
        "schema_version": "codex-first-ablation-v1",
        "arm": arm,
        "retrieval_profile": retrieval_profile(arm),
        "task_topic": task["topic"],
        "task_cutoff": str(task.get("cutoff_date") or ""),
        "prompt_sha256": hashlib.sha256(COMMON_PROMPT.encode()).hexdigest(),
        "author_label": author_label(arm),
        "source_commit": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=source, text=True
        ).strip(),
    }
    (workspace / "run_manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )


def run_arm(
    workspace: Path,
    arm: str,
    model: str,
    effort: str,
    timeout: int,
    prompt_path: Path | None = None,
) -> int:
    env = dict(os.environ)
    tool_path = publication_tool_path(workspace)
    if tool_path:
        env["PATH"] = f"{tool_path}{os.pathsep}{env.get('PATH', '')}"
    if arm != "pure-codex":
        env["REASFLOW_SURVEY_RETRIEVAL_PROFILE"] = retrieval_profile(arm)
        env["REASFLOW_PRIVATE_SKILLS_ROOT"] = str(workspace / ".codex/reasflow-skills")
    command = [
        "codex", "--search", "exec", "--skip-git-repo-check",
        "--sandbox", "danger-full-access", "-m", model,
        "-c", 'approval_policy="never"',
        "-c", f'model_reasoning_effort="{effort}"',
        "-C", str(workspace), "--output-last-message", str(workspace / "last_message.md"), "-",
    ]
    selected_prompt = prompt_path or workspace / "prompt.txt"
    log_name = "repair_exec.log" if prompt_path else "codex_exec.log"
    with selected_prompt.open("r", encoding="utf-8") as prompt, (
        workspace / log_name
    ).open("w", encoding="utf-8") as log:
        try:
            result = subprocess.run(
                command, stdin=prompt, stdout=log, stderr=subprocess.STDOUT,
                text=True, env=env, timeout=timeout, check=False,
            )
            return result.returncode
        except subprocess.TimeoutExpired:
            log.write(f"\nRUNNER_TIMEOUT_SECONDS={timeout}\n")
            return 124


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--task", type=Path, action="append", required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--source", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--arm", choices=ARMS, action="append")
    parser.add_argument("--model", default="gpt-5.6-terra")
    parser.add_argument("--effort", default="high")
    parser.add_argument("--timeout", type=int, default=14400)
    parser.add_argument("--prepare-only", action="store_true")
    parser.add_argument("--repair-existing", action="store_true")
    args = parser.parse_args()
    arms = args.arm or list(ARMS)
    exit_code = 0
    for task_path in args.task:
        task = yaml.safe_load(task_path.read_text(encoding="utf-8")) or {}
        require_public_task(task, task_path)
        slug = task_slug(task, task_path)
        for arm in arms:
            workspace = args.output_root / slug / arm
            if not args.repair_existing:
                prepare_arm(workspace, arm, task, args.source.resolve())
                print(f"prepared {workspace}")
            elif not workspace.is_dir():
                print(f"missing existing workspace {workspace}")
                if not exit_code:
                    exit_code = 2
                continue
            if not args.prepare_only:
                if args.repair_existing:
                    canonicalize_publication_layout(workspace)
                    before = write_publication_validation(workspace)
                    if before["ok"]:
                        code = 0
                    else:
                        repair_path = workspace / "publication_repair_prompt.txt"
                        repair_path.write_text(
                            repair_prompt(before) + "\n", encoding="utf-8"
                        )
                        code = run_arm(
                            workspace,
                            arm,
                            args.model,
                            args.effort,
                            args.timeout,
                            prompt_path=repair_path,
                        )
                else:
                    code = run_arm(workspace, arm, args.model, args.effort, args.timeout)
                print(f"finished arm={arm} task={slug} returncode={code}")
                if code == 0:
                    canonicalize_publication_layout(workspace)
                    validation = write_publication_validation(workspace)
                    if not validation["ok"] and not args.repair_existing:
                        repair_path = workspace / "publication_repair_prompt.txt"
                        repair_path.write_text(
                            repair_prompt(validation) + "\n", encoding="utf-8"
                        )
                        code = run_arm(
                            workspace,
                            arm,
                            args.model,
                            args.effort,
                            args.timeout,
                            prompt_path=repair_path,
                        )
                        if code == 0:
                            canonicalize_publication_layout(workspace)
                            validation = write_publication_validation(workspace)
                    if code == 0 and validation["ok"]:
                        packaged = package_deliverables(workspace, slug, arm)
                        print(f"packaged arm={arm} task={slug} files={packaged}")
                    elif code == 0:
                        print(
                            f"publication gate failed arm={arm} task={slug} "
                            f"validation={validation}"
                        )
                        code = 3
                if code and not exit_code:
                    exit_code = code
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
