#!/usr/bin/env python3

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import re
import sys
import time
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


HERE = Path(__file__).resolve()
REASFLOW_ROOT = HERE.parents[3]
LITERATURE_PATH = (
    REASFLOW_ROOT
    / "survey"
    / "autosurvey-paper-retrieval"
    / "scripts"
    / "autosurvey_literature.py"
)
SCHEMA_VERSION = "1.0"


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


literature = _load_module("reasflow_reascholar_literature", LITERATURE_PATH)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def first_text(*values: Any) -> str:
    for value in values:
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return ""


def text_preview(value: Any, max_chars: int) -> tuple[str, bool, int]:
    text = str(value or "").strip()
    if len(text) <= max_chars:
        return text, False, len(text)
    return text[:max_chars].rstrip() + "\n...[truncated]", True, len(text)


def split_authors(value: Any) -> list[str]:
    if isinstance(value, list):
        authors = []
        for item in value:
            name = item.get("name") if isinstance(item, dict) else item
            if str(name or "").strip():
                authors.append(str(name).strip())
        return authors
    if isinstance(value, str):
        return [
            name.strip()
            for name in re.split(r";|\band\b", value)
            if name.strip()
        ]
    return []


def safe_name(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", value).strip("._")
    return cleaned[:180] or "paper"


def resolve_path(workspace: Path, raw: str) -> Path:
    path = Path(raw)
    return path.resolve() if path.is_absolute() else (workspace / path).resolve()


def display_path(path: Path, workspace: Path) -> str:
    try:
        return str(path.relative_to(workspace))
    except ValueError:
        return str(path)


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected a JSON object in {path}")
    return payload


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def fresh_cache(path: Path, max_age_hours: float) -> bool:
    if not path.is_file() or max_age_hours <= 0:
        return False
    age_seconds = max(0.0, time.time() - path.stat().st_mtime)
    return age_seconds <= max_age_hours * 3600.0


def cached_json(path: Path, max_age_hours: float) -> dict[str, Any] | None:
    if not fresh_cache(path, max_age_hours):
        return None
    try:
        return read_json(path)
    except (OSError, ValueError, json.JSONDecodeError):
        return None


def detail_has_prover(detail: dict[str, Any]) -> bool:
    proof = as_dict(as_dict(detail.get("display")).get("proof"))
    return bool(
        as_list(proof.get("statement_cards"))
        or as_list(proof.get("dependency_edges"))
        or proof.get("statement_count_returned")
    )


def bibtex_year(bibtex: str) -> int | None:
    match = re.search(
        r"\byear\s*=\s*[{\"]?\s*(\d{4})",
        str(bibtex or ""),
        re.IGNORECASE,
    )
    return int(match.group(1)) if match else None


def arxiv_id_from_key(paper_key: str) -> str:
    match = re.match(r"^(\d{4}\.\d{4,5})(?:v\d+)?(?:__|$)", paper_key)
    return match.group(1) if match else ""


def absolute_reascholar_url(value: str) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    if text.startswith(("http://", "https://")):
        return text
    return f"{literature.REASCHOLAR_BASE_URL}/{text.lstrip('/')}"


def paper_links(detail: dict[str, Any], paper_key: str) -> dict[str, str]:
    raw_links = as_dict(detail.get("links"))
    links = {
        key: absolute_reascholar_url(value)
        for key, value in raw_links.items()
        if isinstance(value, str) and value.strip()
    }
    quoted = urllib.parse.quote(paper_key, safe="")
    links.setdefault(
        "structured_detail",
        f"{literature.REASCHOLAR_BASE_URL}/api/search/papers/{quoted}",
    )
    links.setdefault(
        "markdown",
        f"{literature.REASCHOLAR_BASE_URL}/api/papers/{quoted}/markdown",
    )
    return links


def identity_and_warnings(
    result: dict[str, Any],
    detail: dict[str, Any],
) -> tuple[dict[str, Any], list[str]]:
    warnings: list[str] = []
    display = as_dict(detail.get("display"))
    overview = as_dict(display.get("overview"))
    publication = as_dict(overview.get("publication"))
    paper_key = first_text(result.get("paper_key"), detail.get("paper_key"))
    title = first_text(result.get("title"), detail.get("title"))
    authors = split_authors(result.get("authors")) or split_authors(
        publication.get("authors")
    )
    year_value = result.get("year") or publication.get("year")
    try:
        year = int(year_value) if year_value else None
    except (TypeError, ValueError):
        year = None
        warnings.append(f"Unrecognized publication year: {year_value}")

    bibtex = first_text(publication.get("bibtex"))
    bib_year = bibtex_year(bibtex)
    if year and bib_year and year != bib_year:
        warnings.append(
            f"Year conflict: search metadata says {year}, BibTeX says {bib_year}."
        )

    raw_doi = first_text(result.get("doi"), publication.get("doi"))
    doi = raw_doi if raw_doi.startswith("10.") else ""
    if raw_doi and not doi:
        warnings.append(
            f"DOI-like value is not a canonical DOI and was not promoted: {raw_doi}"
        )

    arxiv_id = arxiv_id_from_key(paper_key)
    canonical_url = ""
    if doi:
        canonical_url = f"https://doi.org/{doi}"
    elif arxiv_id:
        canonical_url = f"https://arxiv.org/abs/{arxiv_id}"

    return (
        {
            "paper_key": paper_key,
            "title": title,
            "authors": authors,
            "year": year,
            "bibtex_year": bib_year,
            "doi": doi,
            "arxiv_id": arxiv_id,
            "canonical_url": canonical_url,
            "bibtex": bibtex,
        },
        warnings,
    )


def proof_statements(
    proof: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[str]]:
    statements: list[dict[str, Any]] = []
    warnings: list[str] = []
    macro_pattern = re.compile(
        r"\\(?:def|newcommand|renewcommand|ProvidesPackage|ifCLASS|DeclareOption)\b"
    )
    for card in as_list(proof.get("statement_cards")):
        if not isinstance(card, dict):
            continue
        raw = as_dict(card.get("raw"))
        qa_flags = [str(flag) for flag in as_list(raw.get("qa_flags"))]
        statement = first_text(card.get("statement"), raw.get("content"))
        label = first_text(card.get("label"), raw.get("label"))
        quality = "reviewed_extraction"
        if qa_flags:
            quality = "needs_review"
        if macro_pattern.search(statement) or "macro" in label.lower():
            quality = "rejected_template_content"
            warnings.append(
                f"Proof object {first_text(card.get('object_id'), label)} looks like "
                "LaTeX template content rather than a mathematical statement."
            )
        statement_value, statement_truncated, statement_chars = text_preview(
            statement, 6000
        )
        statements.append(
            {
                "object_id": first_text(card.get("object_id"), raw.get("object_id")),
                "label": label,
                "type": first_text(card.get("type"), raw.get("type")),
                "statement": statement_value,
                "statement_chars": statement_chars,
                "statement_truncated": statement_truncated,
                "context": as_dict(card.get("context"))
                or as_dict(raw.get("source_anchor")),
                "quality": quality,
                "qa_flags": qa_flags,
            }
        )
    return statements, warnings


def normalized_code_snippets(algorithm: dict[str, Any]) -> list[dict[str, Any]]:
    snippets = []
    for item in as_list(algorithm.get("code_snippets")):
        if not isinstance(item, dict):
            continue
        code_preview, code_truncated, code_chars = text_preview(
            item.get("code"), 2000
        )
        snippets.append(
            {
                "target_label": first_text(item.get("target_label")),
                "target_summary": first_text(item.get("target_summary")),
                "repo_url": first_text(item.get("repo_url")),
                "file_path": first_text(item.get("file_path")),
                "start_line": item.get("start_line"),
                "end_line": item.get("end_line"),
                "language": first_text(item.get("language")),
                "reason": first_text(item.get("reason")),
                "matched_terms": as_list(item.get("matched_terms")),
                "score": item.get("score"),
                "code_preview": code_preview,
                "code_chars": code_chars,
                "code_truncated": code_truncated,
            }
        )
    return snippets


def normalize_algorithm_paper(
    result: dict[str, Any],
    detail: dict[str, Any],
    raw_response_path: str,
) -> dict[str, Any]:
    identity, warnings = identity_and_warnings(result, detail)
    display = as_dict(detail.get("display"))
    algorithm = as_dict(display.get("algorithm"))
    problem = as_dict(algorithm.get("problem"))
    method = as_dict(algorithm.get("method"))
    preview = as_dict(as_dict(result.get("schema_match")).get("preview"))
    proof = as_dict(display.get("proof"))
    statements, proof_warnings = proof_statements(proof)
    warnings.extend(proof_warnings)
    code_snippets = normalized_code_snippets(algorithm)
    flags = as_dict(result.get("flags"))

    state_variables = as_list(method.get("state_variables")) or as_list(
        preview.get("state_variables")
    )
    method_payload = {
        "summary": first_text(method.get("summary"), preview.get("summary")),
        "variants": as_list(method.get("variants")) or as_list(preview.get("variants")),
        "state_variables": state_variables,
        "initialization": as_list(method.get("initialization"))
        or as_list(preview.get("initialization")),
        "update_rules": as_list(method.get("update_rules"))
        or as_list(preview.get("update_rules")),
        "design_choices": as_list(method.get("design_choices"))
        or as_list(preview.get("design_choices")),
        "implementation_notes": as_list(method.get("implementation"))
        or as_list(preview.get("implementation")),
    }

    if flags.get("has_algorithm") and not any(
        [
            problem,
            method_payload["summary"],
            method_payload["update_rules"],
        ]
    ):
        warnings.append(
            "Search flags report algorithm content, but structured algorithm details are empty."
        )
    if flags.get("has_code_link") and not code_snippets:
        warnings.append(
            "Search flags report a code link, but no mapped code snippets were returned."
        )
    if flags.get("has_prover") and not statements:
        warnings.append(
            "Search flags report prover data, but no proof statement cards were returned."
        )

    return {
        **identity,
        "rank": result.get("rank"),
        "search_score": result.get("score"),
        "category": first_text(result.get("category")),
        "domain": as_dict(result.get("domain")),
        "flags": flags,
        "algorithm": {
            "problem": {
                "task": first_text(problem.get("task")),
                "setting": first_text(problem.get("setting")),
                "objectives": as_list(problem.get("objectives")),
                "assumptions": as_list(problem.get("assumptions")),
                "constraints": as_list(problem.get("constraints")),
                "tags": as_list(problem.get("tags")),
            },
            "method": method_payload,
        },
        "theory": {
            "statement_count_returned": proof.get("statement_count_returned", 0),
            "has_more_statements": bool(proof.get("has_more_statements")),
            "statements": statements,
            "dependency_edges": as_list(proof.get("dependency_edges")),
        },
        "code_snippets": code_snippets,
        "sources": {
            "raw_response": raw_response_path,
            **paper_links(detail, identity["paper_key"]),
        },
        "warnings": warnings,
    }


def normalized_evaluations(experiment: dict[str, Any]) -> list[dict[str, Any]]:
    evaluations = []
    for item in as_list(experiment.get("evaluations")):
        if not isinstance(item, dict):
            continue
        evaluations.append(
            {
                "name": first_text(item.get("name")),
                "goal": first_text(item.get("goal")),
                "metrics": as_list(item.get("metrics")),
                "settings": as_list(item.get("settings")),
                "reported_findings": as_list(item.get("findings")),
            }
        )
    return evaluations


def normalize_experiment_paper(
    result: dict[str, Any],
    detail: dict[str, Any],
    raw_response_path: str,
) -> dict[str, Any]:
    identity, warnings = identity_and_warnings(result, detail)
    display = as_dict(detail.get("display"))
    algorithm = as_dict(display.get("algorithm"))
    problem = as_dict(algorithm.get("problem"))
    method = as_dict(algorithm.get("method"))
    experiment = as_dict(display.get("experiment"))
    setup = as_dict(experiment.get("setup"))
    datasets = as_list(experiment.get("datasets"))
    baselines = as_list(experiment.get("baselines"))
    evaluations = normalized_evaluations(experiment)
    limitations = as_list(experiment.get("limitations"))
    code_snippets = normalized_code_snippets(algorithm)
    flags = as_dict(result.get("flags"))

    if flags.get("has_experiments") and not any(
        [datasets, baselines, setup, evaluations, limitations]
    ):
        warnings.append(
            "Search flags report experiments, but structured experiment details are empty."
        )
    if flags.get("has_code_link") and not code_snippets:
        warnings.append(
            "Search flags report a code link, but no mapped code snippets were returned."
        )
    if not as_list(setup.get("parameters")):
        warnings.append("No structured experiment parameters were returned.")
    if not evaluations:
        warnings.append("No structured evaluation records were returned.")

    return {
        **identity,
        "rank": result.get("rank"),
        "search_score": result.get("score"),
        "category": first_text(result.get("category")),
        "domain": as_dict(result.get("domain")),
        "flags": flags,
        "algorithm_context": {
            "task": first_text(problem.get("task")),
            "assumptions": as_list(problem.get("assumptions")),
            "constraints": as_list(problem.get("constraints")),
            "variants": as_list(method.get("variants")),
        },
        "experiment": {
            "datasets": datasets,
            "baselines": baselines,
            "setup": {
                "environment": as_list(setup.get("environment")),
                "parameters": as_list(setup.get("parameters")),
            },
            "evaluations": evaluations,
            "limitations": limitations,
        },
        "code_snippets": code_snippets,
        "sources": {
            "raw_response": raw_response_path,
            **paper_links(detail, identity["paper_key"]),
        },
        "warnings": warnings,
    }


def normalize_theorem_hits(payload: dict[str, Any]) -> list[dict[str, Any]]:
    hits = []
    for item in as_list(payload.get("results")):
        if not isinstance(item, dict) or item.get("result_type") != "statement":
            continue
        raw = as_dict(item.get("raw"))
        statement, statement_truncated, statement_chars = text_preview(
            first_text(item.get("statement"), raw.get("statement")),
            6000,
        )
        hits.append(
            {
                "rank": item.get("rank"),
                "score": item.get("score"),
                "paper_key": first_text(raw.get("paper_key")),
                "paper_title": first_text(raw.get("title")),
                "object_id": first_text(raw.get("object_id")),
                "label": first_text(item.get("label"), raw.get("label")),
                "statement_type": first_text(
                    item.get("statement_type"), raw.get("type")
                ),
                "statement": statement,
                "statement_chars": statement_chars,
                "statement_truncated": statement_truncated,
                "context": as_dict(item.get("context"))
                or as_dict(raw.get("context")),
                "source": item.get("source"),
            }
        )
    return hits


def build_filters(args: argparse.Namespace) -> dict[str, Any]:
    filters: dict[str, Any] = {}
    if args.evidence_type == "algorithm":
        filters["has_algorithm"] = True
        if args.require_theory:
            filters["has_theory"] = True
    else:
        filters["has_experiments"] = True
    if args.require_code:
        filters["has_code_link"] = True
    if args.year_from:
        filters["year_from"] = args.year_from
    if args.year_to:
        filters["year_to"] = args.year_to
    return filters


def search_request(args: argparse.Namespace) -> dict[str, Any]:
    return {
        "query": args.query,
        "top_k": args.top_k,
        "mode": "algorithm" if args.evidence_type == "algorithm" else "fast",
        "response_format": "structured",
        "include_details": False,
        "filters": build_filters(args),
    }


def raw_search_name(evidence_type: str, request: dict[str, Any]) -> str:
    digest = hashlib.sha256(
        json.dumps(request, sort_keys=True).encode("utf-8")
    ).hexdigest()[:12]
    return f"{evidence_type}_search_{digest}.json"


def append_manifest(path: Path, record: dict[str, Any]) -> None:
    payload: dict[str, Any] = {"schema_version": SCHEMA_VERSION, "runs": []}
    if path.exists():
        loaded = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(loaded, dict) or not isinstance(loaded.get("runs"), list):
            raise ValueError(f"Invalid retrieval manifest: {path}")
        payload = loaded
    payload["runs"].append(record)
    write_json(path, payload)


def retrieve_evidence(args: argparse.Namespace) -> dict[str, Any]:
    workspace = Path(args.workspace).resolve()
    output = resolve_path(workspace, args.output)
    raw_dir = resolve_path(workspace, args.raw_dir)
    manifest_path = resolve_path(workspace, args.manifest)
    request = search_request(args)
    search_raw_path = raw_dir / raw_search_name(args.evidence_type, request)
    search_payload = None if args.refresh_cache else cached_json(
        search_raw_path, args.cache_max_age_hours
    )
    search_cache_hit = search_payload is not None
    if search_payload is None:
        search_payload = literature.post_reascholar_json("/api/search", request)
        write_json(search_raw_path, search_payload)

    results = [
        item
        for item in as_list(search_payload.get("results"))
        if isinstance(item, dict) and item.get("result_type") == "paper"
    ]
    papers = []
    retrieval_warnings: list[str] = []
    raw_detail_paths: list[str] = []
    detail_cache_hits = 0
    detail_network_fetches = 0
    raw_hashes = {
        display_path(search_raw_path, workspace): sha256_file(search_raw_path)
    }
    for result in results[: args.detail_top_k]:
        paper_key = first_text(result.get("paper_key"))
        if not paper_key:
            retrieval_warnings.append(
                "Skipped a paper result because it had no paper_key."
            )
            continue
        raw_detail_path = raw_dir / f"{safe_name(paper_key)}.json"
        require_prover = args.evidence_type == "algorithm" and not args.no_proof
        detail = None if args.refresh_cache else cached_json(
            raw_detail_path, args.cache_max_age_hours
        )
        if detail is not None and require_prover and not detail_has_prover(detail):
            detail = None
        if detail is not None:
            detail_cache_hits += 1
        else:
            try:
                detail = literature.get_reascholar_json(
                    f"/api/search/papers/{urllib.parse.quote(paper_key, safe='')}",
                    {
                        "include_markdown": "false",
                        "include_prover": "true" if require_prover else "false",
                        "statement_limit": (
                            args.statement_limit if require_prover else 1
                        ),
                    },
                )
                detail_network_fetches += 1
                write_json(raw_detail_path, detail)
            except Exception as exc:
                retrieval_warnings.append(
                    f"Detail retrieval failed for {paper_key}: {exc}"
                )
                continue
        displayed_raw_path = display_path(raw_detail_path, workspace)
        raw_detail_paths.append(displayed_raw_path)
        raw_hashes[displayed_raw_path] = sha256_file(raw_detail_path)
        if args.evidence_type == "algorithm":
            paper = normalize_algorithm_paper(result, detail, displayed_raw_path)
        else:
            paper = normalize_experiment_paper(result, detail, displayed_raw_path)
        papers.append(paper)

    theorem_hits: list[dict[str, Any]] = []
    theorem_search_path = ""
    theorem_cache_hit = False
    if args.evidence_type == "algorithm" and not args.no_theorem_search:
        theorem_request = {
            "query": f"{args.query} convergence assumptions",
            "top_k": args.theorem_top_k,
            "mode": "theorem",
            "response_format": "structured",
        }
        try:
            theorem_raw_path = raw_dir / raw_search_name("theorem", theorem_request)
            theorem_payload = None if args.refresh_cache else cached_json(
                theorem_raw_path, args.cache_max_age_hours
            )
            theorem_cache_hit = theorem_payload is not None
            if theorem_payload is None:
                theorem_payload = literature.post_reascholar_json(
                    "/api/search", theorem_request
                )
                write_json(theorem_raw_path, theorem_payload)
            theorem_search_path = display_path(theorem_raw_path, workspace)
            raw_hashes[theorem_search_path] = sha256_file(theorem_raw_path)
            theorem_hits = normalize_theorem_hits(theorem_payload)
        except Exception as exc:
            retrieval_warnings.append(f"Theorem search failed: {exc}")

    generated_at = utc_now()
    if papers:
        retrieval_status = "partial" if retrieval_warnings else "ok"
    elif results:
        retrieval_status = "partial"
    else:
        retrieval_status = "empty"
    if not results:
        retrieval_warnings.append(
            "ReaScholar returned no paper results matching the required filters."
        )
    payload = {
        "schema_version": SCHEMA_VERSION,
        "evidence_type": args.evidence_type,
        "generated_at": generated_at,
        "retrieval_status": retrieval_status,
        "provider": "ReaScholar",
        "base_url": literature.REASCHOLAR_BASE_URL,
        "query": args.query,
        "request": request,
        "paper_result_count": len(results),
        "paper_detail_count": len(papers),
        "papers": papers,
        "theorem_hits": theorem_hits,
        "raw_search_response": display_path(search_raw_path, workspace),
        "raw_theorem_response": theorem_search_path,
        "cache": {
            "max_age_hours": args.cache_max_age_hours,
            "refresh_requested": bool(args.refresh_cache),
            "search_cache_hit": search_cache_hit,
            "detail_cache_hits": detail_cache_hits,
            "detail_network_fetches": detail_network_fetches,
            "theorem_cache_hit": theorem_cache_hit,
        },
        "raw_response_sha256": raw_hashes,
        "warnings": retrieval_warnings,
    }
    write_json(output, payload)
    append_manifest(
        manifest_path,
        {
            "generated_at": generated_at,
            "evidence_type": args.evidence_type,
            "query": args.query,
            "output": display_path(output, workspace),
            "retrieval_status": payload["retrieval_status"],
            "paper_detail_count": len(papers),
            "raw_search_response": display_path(search_raw_path, workspace),
            "raw_detail_responses": raw_detail_paths,
            "raw_theorem_response": theorem_search_path,
            "cache": payload["cache"],
            "raw_response_sha256": raw_hashes,
        },
    )
    return payload


def error_payload(args: argparse.Namespace, message: str) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "evidence_type": args.evidence_type,
        "generated_at": utc_now(),
        "retrieval_status": "error",
        "provider": "ReaScholar",
        "query": args.query,
        "papers": [],
        "theorem_hits": [],
        "warnings": [message],
    }


def add_common_args(
    command: argparse.ArgumentParser,
    evidence_type: str,
) -> None:
    command.set_defaults(evidence_type=evidence_type)
    command.add_argument("--workspace", default=".")
    command.add_argument("--query", required=True)
    command.add_argument("--top-k", type=int, default=5 if evidence_type == "algorithm" else 8)
    command.add_argument(
        "--detail-top-k",
        type=int,
        default=3 if evidence_type == "algorithm" else 5,
    )
    command.add_argument(
        "--output",
        default=(
            "Alg_Exp/evidence/algorithm_evidence.json"
            if evidence_type == "algorithm"
            else "Alg_Exp/evidence/experiment_evidence.json"
        ),
    )
    command.add_argument("--raw-dir", default="Alg_Exp/evidence/raw")
    command.add_argument(
        "--manifest", default="Alg_Exp/evidence/retrieval_manifest.json"
    )
    command.add_argument(
        "--cache-max-age-hours",
        type=float,
        default=168.0,
        help="Reuse valid search/detail responses newer than this many hours.",
    )
    command.add_argument(
        "--refresh-cache",
        action="store_true",
        help="Ignore existing raw responses and fetch fresh evidence.",
    )
    command.add_argument("--require-code", action="store_true")
    command.add_argument("--year-from", type=int)
    command.add_argument("--year-to", type=int)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Retrieve traceable algorithm or experiment evidence from ReaScholar "
            "without flattening structured paper details."
        )
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    algorithm = subparsers.add_parser(
        "algorithm", help="Retrieve algorithm, theory, and code evidence"
    )
    add_common_args(algorithm, "algorithm")
    algorithm.add_argument("--require-theory", action="store_true")
    algorithm.add_argument("--no-proof", action="store_true")
    algorithm.add_argument("--statement-limit", type=int, default=12)
    algorithm.add_argument("--no-theorem-search", action="store_true")
    algorithm.add_argument("--theorem-top-k", type=int, default=5)

    experiment = subparsers.add_parser(
        "experiment", help="Retrieve dataset, baseline, setup, and evaluation evidence"
    )
    add_common_args(experiment, "experiment")
    experiment.set_defaults(
        require_theory=False,
        no_proof=True,
        statement_limit=1,
        no_theorem_search=True,
        theorem_top_k=0,
    )
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    if args.top_k < 1 or args.top_k > 100:
        parser.error("--top-k must be between 1 and 100")
    if args.detail_top_k < 1 or args.detail_top_k > args.top_k:
        parser.error("--detail-top-k must be between 1 and --top-k")
    if args.cache_max_age_hours < 0:
        parser.error("--cache-max-age-hours must be non-negative")
    try:
        payload = retrieve_evidence(args)
    except Exception as exc:
        message = f"ReaScholar retrieval failed: {exc}"
        workspace = Path(args.workspace).resolve()
        output = resolve_path(workspace, args.output)
        write_json(output, error_payload(args, message))
        print(message, file=sys.stderr)
        return 1
    print(
        json.dumps(
            {
                "output": str(resolve_path(Path(args.workspace).resolve(), args.output)),
                "retrieval_status": payload["retrieval_status"],
                "paper_detail_count": payload["paper_detail_count"],
                "theorem_hit_count": len(payload["theorem_hits"]),
            },
            indent=2,
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
