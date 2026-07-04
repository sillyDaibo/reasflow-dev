#!/usr/bin/env python3
"""Extract structured information from workspace files for Introduction writing.

Migrated from agentscope-intro-main/agentscope_intro/tools/extraction_tools.py.
Modes: survey | method | experiment | theory | organize
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.request
from pathlib import Path

DEFAULT_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
DEFAULT_API_KEY = os.getenv("OPENAI_API_KEY", "")
DEFAULT_MODEL = os.getenv("OPENAI_MODEL", "gpt-5.4")

SYSTEM_PROMPT = (
    "You are an information extraction assistant. Extract structured information "
    "from research documents for writing academic paper introductions.\n"
    "Rules: (1) Extract ONLY explicitly stated information. "
    "(2) Do NOT invent or hallucinate. "
    "(3) Use empty strings/arrays for missing fields. "
    "(4) Output valid JSON only."
)

EXTRACT_PROMPTS: dict[str, str] = {
    "survey": """Extract Introduction-relevant information from this literature survey.

Extract:
1. Research background: field, importance, applications
2. Related work categories: each category name, description, representative works
   (method name, paper title, authors, year, arxiv_id, bibtex_key, key contribution, applicable scenarios)
3. Gaps: gap description, affected methods, evidence, impact
4. Citations: bibtex_key, paper_title, authors

Output JSON:
{
  "background": {"research_field": "", "importance": "", "applications": []},
  "related_works": {"categories": [{"category_name": "", "description": "", "representative_works": [
    {"method_name": "", "paper_title": "", "authors": "", "year": "", "arxiv_id": "", "bibtex_key": "", "key_contribution": "", "applicable_scenarios": ""}
  ]}]},
  "gaps": [{"gap_description": "", "affected_methods": "", "evidence": "", "impact": ""}],
  "citations": [{"bibtex_key": "", "paper_title": "", "authors": ""}]
}""",

    "method": """Extract Introduction-relevant information from this method description.

Extract:
1. Method summary: core idea, key steps, key techniques
2. Innovations: innovation description, significance
3. Contributions: contribution, addresses_gap, value
4. Differences vs existing methods: main differences, why important, advantages

Output JSON:
{
  "method_summary": {"core_idea": "", "key_steps": [], "key_techniques": []},
  "innovations": [{"innovation": "", "significance": ""}],
  "contributions": [{"contribution": "", "addresses_gap": "", "value": ""}],
  "differences": {"vs_existing_methods": "", "why_important": "", "advantages": ""}
}""",

    "experiment": """Extract Introduction-relevant information from these experiment results.

Extract:
1. Key results: description, significance
2. Performance metrics: metric name, value (only explicit values), baseline value, improvement
3. Baseline comparison: baselines, improvements per metric
4. Validation: datasets, scenarios, experimental setup

IMPORTANT: Never fabricate numeric values. Use descriptive text if numbers are not explicit.

Output JSON:
{
  "key_results": [{"result_description": "", "significance": ""}],
  "performance_metrics": [{"metric_name": "", "value": "", "baseline_value": "", "improvement": ""}],
  "baseline_comparison": {"baselines": [], "improvements": [{"metric": "", "improvement_description": "", "improvement_value": ""}]},
  "validation": {"datasets": [], "scenarios": [], "experimental_setup": ""}
}""",

    "theory": """Extract Introduction-relevant information from this theoretical work.

Extract:
1. Theoretical contributions: contribution, problem solved, innovation
2. Key theorems/lemmas: name, statement, significance, conditions
3. Convergence analysis: convergence rate (only explicit), conditions, significance
4. Complexity analysis: time/space complexity (only explicit), significance
5. Theoretical advantages vs existing theory

IMPORTANT: Never fabricate theorems or complexity bounds not in the text.

Output JSON:
{
  "theoretical_contributions": [{"contribution": "", "problem_solved": "", "innovation": ""}],
  "key_theorems": [{"theorem_name": "", "statement": "", "significance": "", "conditions": ""}],
  "convergence_analysis": {"convergence_rate": "", "convergence_conditions": "", "significance": ""},
  "complexity_analysis": {"time_complexity": "", "space_complexity": "", "significance": ""},
  "theoretical_advantages": {"advantages": [], "vs_existing_theory": ""}
}""",
}


def _preprocess_tex(content: str) -> str:
    lines = []
    for line in content.split("\n"):
        if "%" in line:
            line = line[:line.index("%")]
        lines.append(line.rstrip())
    text = "\n".join(lines)
    text = re.sub(r"\\label\{[^}]*\}", "", text)
    text = re.sub(r"\\cite\{([^}]*)\}", r"[CITE:\1]", text)
    text = re.sub(r"\\ref\{[^}]*\}", "", text)
    text = re.sub(r"\\(sub)*section\{([^}]*)\}", r"\n### \2\n", text)
    for cmd in ("textbf", "textit", "emph"):
        text = re.sub(rf"\\{cmd}\{{([^}}]*)\}}", r"\1", text)
    return text


def _read_source(path: str, workspace: Path) -> tuple[str, str | None]:
    """Return (content, error_json). If directory, reads top files."""
    full = (workspace / path).resolve()
    if not str(full).startswith(str(workspace)):
        return "", json.dumps({"error": f"Path outside workspace: {path}", "extracted": {}})
    if not full.exists():
        return "", json.dumps({"error": f"Path not found: {path}", "extracted": {}})
    if full.is_dir():
        supported = {".md", ".tex", ".txt", ".json", ".py", ".bib", ".rst", ".yaml", ".yml"}
        files = sorted(
            (f for f in full.rglob("*") if f.is_file() and f.suffix.lower() in supported
             and not any(p in f.parts for p in (".git", "__pycache__", ".venv", "node_modules"))),
            key=lambda f: ({".md": 0, ".tex": 1, ".bib": 2, ".json": 3}.get(f.suffix.lower(), 4)),
        )[:10]
        if not files:
            return "", json.dumps({"error": f"No readable files in directory: {path}", "extracted": {}})
        parts = []
        for f in files:
            try:
                text = f.read_text(encoding="utf-8")
                if f.suffix.lower() == ".tex":
                    text = _preprocess_tex(text)
                parts.append(f"\n\n=== {f.relative_to(full)} ===\n{text}")
            except Exception:
                continue
        return "\n".join(parts), None
    try:
        content = full.read_text(encoding="utf-8")
        if path.endswith(".tex"):
            content = _preprocess_tex(content)
        return content, None
    except Exception as exc:
        return "", json.dumps({"error": str(exc), "extracted": {}})


def _parse_json(text: str) -> dict:
    m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    try:
        return json.loads(m.group(1) if m else text)
    except json.JSONDecodeError:
        return {"parse_error": "could not parse JSON", "raw_response": text[:500]}


def _call_llm(system: str, user: str, base_url: str, api_key: str, model: str) -> str:
    payload = json.dumps({
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "stream": True,
        "temperature": 0.3,
    }).encode("utf-8")
    req = urllib.request.Request(
        f"{base_url.rstrip('/')}/chat/completions",
        data=payload,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "User-Agent": "openai-python/1.0",
        },
        method="POST",
    )
    chunks: list[str] = []
    with urllib.request.urlopen(req, timeout=120) as resp:
        for raw in resp:
            line = raw.decode("utf-8").strip()
            if not line.startswith("data:"):
                continue
            data = line[len("data:"):].strip()
            if data == "[DONE]":
                break
            try:
                delta = json.loads(data)["choices"][0]["delta"].get("content", "")
                if delta:
                    chunks.append(delta)
            except (KeyError, IndexError, json.JSONDecodeError):
                continue
    return "".join(chunks)


def cmd_extract(mode: str, args: argparse.Namespace) -> int:
    workspace = Path(args.workspace).resolve()
    content, err = _read_source(args.source, workspace)
    if err:
        print(err)
        return 1

    prompt_base = EXTRACT_PROMPTS[mode]
    if args.focus:
        prompt_base += f"\n\nFocus especially on: {args.focus}"
    user_prompt = f"{prompt_base}\n\n---\n\n## Source content:\n\n```\n{content[:8000]}\n```\n\nOutput JSON only."

    try:
        response = _call_llm(SYSTEM_PROMPT, user_prompt, args.base_url, args.api_key, args.model)
    except Exception as exc:
        print(json.dumps({"error": str(exc), "source_type": mode, "source_path": args.source, "extracted": {}}))
        return 1

    result = {
        "source_type": mode,
        "source_path": args.source,
        "extracted": _parse_json(response),
    }
    output = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output:
        Path(args.output).write_text(output, encoding="utf-8")
    print(output)
    return 0


def cmd_organize(args: argparse.Namespace) -> int:
    parsed: list[dict] = []
    for inp in args.inputs:
        try:
            parsed.append(json.loads(Path(inp).read_text(encoding="utf-8")))
        except Exception as exc:
            print(f"WARNING: could not read {inp}: {exc}", file=sys.stderr)

    survey = next((p.get("extracted", {}) for p in parsed if p.get("source_type") == "survey"), None)
    method = next((p.get("extracted", {}) for p in parsed if p.get("source_type") == "method"), None)
    experiment = next((p.get("extracted", {}) for p in parsed if p.get("source_type") == "experiment"), None)
    theory = next((p.get("extracted", {}) for p in parsed if p.get("source_type") == "theory"), None)

    organized: dict[str, object] = {
        "problem_background": "",
        "related_works": "",
        "method_summary": "",
        "results_preview": "",
        "citations": [],
    }

    if survey:
        bg = survey.get("background", {})
        if isinstance(bg, dict):
            organized["problem_background"] = (
                f"Field: {bg.get('research_field', '')}\n"
                f"Importance: {bg.get('importance', '')}\n"
                f"Applications: {', '.join(bg.get('applications', []))}"
            )
        rw_parts: list[str] = []
        for cat in survey.get("related_works", {}).get("categories", []):
            rw_parts.append(f"\n### {cat.get('category_name', '')}")
            if cat.get("description"):
                rw_parts.append(cat["description"])
            for work in cat.get("representative_works", []):
                bits = [f"{k}: {work[k]}" for k in ("method_name", "paper_title", "authors", "year", "arxiv_id", "key_contribution") if work.get(k)]
                if bits:
                    rw_parts.append("- " + " | ".join(bits))
        gaps = survey.get("gaps", [])
        if gaps:
            rw_parts.append("\n### Limitations of existing methods:")
            for i, gap in enumerate(gaps, 1):
                rw_parts.append(f"{i}. {gap.get('gap_description', '')}" + (f" (Impact: {gap['impact']})" if gap.get("impact") else ""))
        organized["related_works"] = "\n".join(rw_parts)
        organized["citations"] = survey.get("citations", [])  # type: ignore[assignment]

    if method:
        ms = method.get("method_summary", {})
        parts: list[str] = []
        if ms.get("core_idea"):
            parts.append(f"Core idea: {ms['core_idea']}")
        if ms.get("key_steps"):
            parts.append(f"Key steps: {'; '.join(ms['key_steps'])}")
        for i, c in enumerate(method.get("contributions", []), 1):
            if c.get("contribution"):
                parts.append(f"{i}. {c['contribution']}")
        organized["method_summary"] = "\n".join(parts)

    res_parts: list[str] = []
    if experiment:
        for r in experiment.get("key_results", []):
            if r.get("result_description"):
                res_parts.append(f"- {r['result_description']}")
        for m in experiment.get("performance_metrics", []):
            if m.get("metric_name") and m.get("value"):
                s = f"- {m['metric_name']}: {m['value']}"
                if m.get("improvement"):
                    s += f" (improvement: {m['improvement']})"
                res_parts.append(s)
    if theory:
        for c in theory.get("theoretical_contributions", []):
            if c.get("contribution"):
                res_parts.append(f"- {c['contribution']}")
        cr = theory.get("convergence_analysis", {}).get("convergence_rate", "")
        if cr:
            res_parts.append(f"Convergence: {cr}")
    organized["results_preview"] = "\n".join(res_parts)

    result = {
        "organized_info": organized,
        "source_summary": {
            t: [p.get("source_path") for p in parsed if p.get("source_type") == t]
            for t in ("survey", "method", "experiment", "theory")
        },
    }
    output = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output:
        Path(args.output).write_text(output, encoding="utf-8")
    print(output)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Extract structured info from workspace files")
    parser.add_argument("--mode", required=True, choices=["survey", "method", "experiment", "theory", "organize"])
    parser.add_argument("--workspace", default=".")
    parser.add_argument("--source", default="", help="Source file/dir (relative to workspace); required for extract modes")
    parser.add_argument("--inputs", nargs="+", default=[], help="JSON files from extract modes; required for organize mode")
    parser.add_argument("--focus", default="", help="Comma-separated focus areas")
    parser.add_argument("--output", default="", help="Write JSON result to this path")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--api-key", default=DEFAULT_API_KEY)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    args = parser.parse_args()

    if args.mode == "organize":
        if not args.inputs:
            print("ERROR: --inputs required for organize mode", file=sys.stderr)
            return 1
        return cmd_organize(args)

    if not args.source:
        print("ERROR: --source required for extract modes", file=sys.stderr)
        return 1
    if not args.api_key:
        print("ERROR: OPENAI_API_KEY not set", file=sys.stderr)
        return 1
    return cmd_extract(args.mode, args)


if __name__ == "__main__":
    raise SystemExit(main())
