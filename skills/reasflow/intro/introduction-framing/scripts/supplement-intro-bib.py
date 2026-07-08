#!/usr/bin/env python3
from __future__ import annotations

import argparse
import difflib
import importlib.util
import json
import os
import re
from pathlib import Path
from typing import Any


def _load_module(module_name: str, module_path: Path):
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load module from {module_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


HERE = Path(__file__).resolve()
REASFLOW_ROOT = HERE.parents[3]
LITERATURE_PATH = (
    REASFLOW_ROOT
    / "survey"
    / "autosurvey-paper-retrieval"
    / "scripts"
    / "autosurvey_literature.py"
)
TOOLS_PATH = (
    REASFLOW_ROOT
    / "survey"
    / "autosurvey-execution"
    / "scripts"
    / "autosurvey_tools.py"
)

literature = _load_module("reasflow_intro_literature", LITERATURE_PATH)
tools = _load_module("reasflow_intro_autosurvey_tools", TOOLS_PATH)


def ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def load_json_file(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def collect_candidates(node: Any, source_path: str, out: list[dict[str, str]]) -> None:
    if isinstance(node, dict):
        title = str(node.get("paper_title") or node.get("title") or "").strip()
        bibtex_key = str(node.get("bibtex_key") or "").strip()
        arxiv_id = str(node.get("arxiv_id") or "").strip()
        doi = str(node.get("doi") or "").strip()
        if title or bibtex_key or arxiv_id or doi:
            out.append(
                {
                    "paper_title": title,
                    "bibtex_key": bibtex_key,
                    "arxiv_id": arxiv_id,
                    "doi": doi,
                    "source_path": source_path,
                }
            )
        for value in node.values():
            collect_candidates(value, source_path, out)
        return
    if isinstance(node, list):
        for item in node:
            collect_candidates(item, source_path, out)


def normalize_candidates(
    json_paths: list[Path],
    explicit_papers: list[str],
) -> list[dict[str, str]]:
    candidates: list[dict[str, str]] = []
    for path in json_paths:
        try:
            collect_candidates(load_json_file(path), str(path), candidates)
        except Exception:
            continue
    for paper in explicit_papers:
        query = str(paper or "").strip()
        if not query:
            continue
        candidates.append(
            {
                "paper_title": query,
                "bibtex_key": "",
                "arxiv_id": "",
                "doi": "",
                "source_path": "cli",
            }
        )

    deduped: list[dict[str, str]] = []
    seen: set[str] = set()
    for candidate in candidates:
        identity = "|".join(
            [
                candidate.get("bibtex_key", "").strip().lower(),
                candidate.get("arxiv_id", "").strip().lower(),
                candidate.get("doi", "").strip().lower(),
                candidate.get("paper_title", "").strip().lower(),
            ]
        )
        if identity == "|||":
            continue
        if identity in seen:
            continue
        seen.add(identity)
        deduped.append(candidate)
    return deduped


def lookup_paper(
    query: str,
    source: str,
    reascholar_mode: str,
    no_s2_supplement: bool,
) -> dict[str, Any] | None:
    paper = None
    if source in {"auto", "reascholar"}:
        try:
            paper = literature.find_reascholar_paper(query, reascholar_mode)
        except Exception:
            paper = None

    if paper is None and source in {"auto", "semantic_scholar"}:
        normalized = literature.normalize_paper_id(query)
        try:
            if normalized.startswith("arXiv:") or normalized.startswith("DOI:"):
                paper = literature.s2_lookup_paper(normalized)
            else:
                paper = literature.s2_search_one(query)
        except Exception:
            paper = None
        if paper:
            paper["source"] = "semantic_scholar"
            paper["sources"] = ["semantic_scholar"]

    if (
        paper
        and source in {"auto", "reascholar"}
        and not no_s2_supplement
        and os.getenv("SEMANTIC_SCHOLAR_API_KEY", "").strip()
    ):
        paper = literature.supplement_with_s2(paper)
    return paper


def choose_query(candidate: dict[str, str]) -> str:
    for field in ("arxiv_id", "doi", "paper_title"):
        value = str(candidate.get(field) or "").strip()
        if value:
            return value
    return ""


def _normalize_title(text: str) -> str:
    return " ".join(re.findall(r"[a-z0-9]+", str(text or "").lower()))


def _title_match_is_strong(query_title: str, matched_title: str) -> bool:
    query_norm = _normalize_title(query_title)
    matched_norm = _normalize_title(matched_title)
    if not query_norm or not matched_norm:
        return False
    ratio = difflib.SequenceMatcher(None, query_norm, matched_norm).ratio()
    query_tokens = set(query_norm.split())
    matched_tokens = set(matched_norm.split())
    if not query_tokens or not matched_tokens:
        return False
    recall = len(query_tokens & matched_tokens) / len(query_tokens)
    return ratio >= 0.82 or recall >= 0.85


def ensure_unique_key(key: str, used_keys: set[str]) -> str:
    if key not in used_keys:
        used_keys.add(key)
        return key
    suffix = 2
    while f"{key}{suffix}" in used_keys:
        suffix += 1
    final_key = f"{key}{suffix}"
    used_keys.add(final_key)
    return final_key


def main() -> int:
    parser = argparse.ArgumentParser(description="Supplement introduction BibTeX")
    parser.add_argument("--workspace", default=".")
    parser.add_argument("--tex", default="")
    parser.add_argument("--bib-input", default="")
    parser.add_argument("--bib-output", required=True)
    parser.add_argument("--citation-json", action="append", default=[])
    parser.add_argument("--paper", action="append", default=[])
    parser.add_argument(
        "--source",
        default="auto",
        choices=["auto", "reascholar", "semantic_scholar"],
    )
    parser.add_argument(
        "--reascholar-mode",
        default="fast",
        choices=["fast", "deep"],
    )
    parser.add_argument("--no-s2-supplement", action="store_true")
    parser.add_argument("--trace-output", default="")
    args = parser.parse_args()

    workspace = Path(args.workspace).resolve()
    bib_input_path = (
        (workspace / args.bib_input).resolve()
        if args.bib_input and not Path(args.bib_input).is_absolute()
        else Path(args.bib_input).resolve() if args.bib_input else None
    )
    bib_output_path = (
        (workspace / args.bib_output).resolve()
        if not Path(args.bib_output).is_absolute()
        else Path(args.bib_output).resolve()
    )
    tex_path = (
        (workspace / args.tex).resolve()
        if args.tex and not Path(args.tex).is_absolute()
        else Path(args.tex).resolve() if args.tex else None
    )

    existing_entries = (
        tools.parse_bib_entries(bib_input_path)
        if bib_input_path and bib_input_path.exists()
        else {}
    )
    existing_text = (
        bib_input_path.read_text(encoding="utf-8").rstrip()
        if bib_input_path and bib_input_path.exists()
        else ""
    )
    used_keys = set(existing_entries.keys())

    json_paths = []
    for raw in args.citation_json:
        path = Path(raw)
        if not path.is_absolute():
            path = (workspace / raw).resolve()
        json_paths.append(path)
    candidates = normalize_candidates(json_paths, args.paper)

    traces: list[dict[str, Any]] = []
    new_entries: list[str] = []

    for candidate in candidates:
        desired_key = str(candidate.get("bibtex_key") or "").strip()
        if desired_key and desired_key in existing_entries:
            traces.append(
                {
                    "status": "existing",
                    "key": desired_key,
                    "query": choose_query(candidate),
                    "source_path": candidate.get("source_path", ""),
                }
            )
            continue

        query = choose_query(candidate)
        if not query:
            traces.append(
                {
                    "status": "skipped",
                    "key": desired_key,
                    "query": "",
                    "source_path": candidate.get("source_path", ""),
                }
            )
            continue

        paper = lookup_paper(
            query,
            args.source,
            args.reascholar_mode,
            args.no_s2_supplement,
        )
        if (
            paper
            and not candidate.get("arxiv_id")
            and not candidate.get("doi")
            and candidate.get("paper_title")
            and not _title_match_is_strong(
                str(candidate.get("paper_title") or ""),
                str(paper.get("title") or ""),
            )
        ):
            paper = None
        if not paper:
            traces.append(
                {
                    "status": "unresolved",
                    "key": desired_key,
                    "query": query,
                    "source_path": candidate.get("source_path", ""),
                }
            )
            continue

        fallback_key = desired_key or None
        selected_key, bibtex = tools.select_bibtex_entry(paper, fallback_key)
        final_key = desired_key
        if not final_key or tools.is_weak_bibtex_key(final_key):
            final_key = selected_key
        if not final_key:
            final_key = tools.generate_bibtex_key(paper)
        final_key = ensure_unique_key(final_key, used_keys)
        bibtex = tools.replace_bibtex_key(bibtex, final_key)
        new_entries.append(bibtex.strip())
        traces.append(
            {
                "status": "supplemented",
                "key": final_key,
                "query": query,
                "paper_title": str(paper.get("title") or ""),
                "source": str(paper.get("source") or ""),
                "sources": paper.get("sources") if isinstance(paper.get("sources"), list) else [],
                "source_path": candidate.get("source_path", ""),
            }
        )

    output_parts = []
    if existing_text:
        output_parts.append(existing_text)
    if new_entries:
        output_parts.append("\n\n".join(new_entries))
    output_text = "\n\n".join(part for part in output_parts if part).strip()
    if output_text:
        output_text += "\n"

    ensure_parent(bib_output_path)
    bib_output_path.write_text(output_text, encoding="utf-8")

    output_keys, _ = tools.parse_bib_keys(bib_output_path) if output_text else (set(), [])
    undefined_citations: list[str] = []
    if tex_path and tex_path.exists():
        cited_keys = tools.parse_cite_keys(tex_path)
        undefined_citations = sorted(cited_keys - output_keys)

    result = {
        "bib_output": str(bib_output_path),
        "existing_entries": len(existing_entries),
        "new_entries": len(new_entries),
        "undefined_citations": undefined_citations,
        "lookup_order": ["reascholar", "semantic_scholar"]
        if args.source == "auto"
        else [args.source],
        "traces": traces,
    }

    if args.trace_output:
        trace_path = Path(args.trace_output)
        if not trace_path.is_absolute():
            trace_path = (workspace / args.trace_output).resolve()
        ensure_parent(trace_path)
        trace_path.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")

    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
