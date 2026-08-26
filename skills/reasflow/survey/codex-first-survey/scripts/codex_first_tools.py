#!/usr/bin/env python3
"""Compact evidence, canonical registry, and audit tools for Codex-first surveys."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Iterable


SCHEMA_VERSION = "codex-first-survey-v1"
TOKEN_STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "based", "by", "for", "from",
    "in", "is", "method", "methods", "of", "on", "optimization", "the",
    "to", "using", "via", "with",
}


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def values(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    if not isinstance(value, dict):
        return []
    for key in ("data", "papers", "results", "items"):
        if isinstance(value.get(key), list):
            return value[key]
    if value.get("title"):
        return [value]
    return []


def load_records(path: Path) -> list[dict[str, Any]]:
    if path.suffix == ".jsonl":
        records = []
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                value = json.loads(line)
                if isinstance(value, dict):
                    records.append(value)
        return records
    return [item for item in values(read_json(path)) if isinstance(item, dict)]


def write_jsonl(path: Path, records: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(record, ensure_ascii=False) + "\n" for record in records),
        encoding="utf-8",
    )


def normalize_text(value: Any) -> str:
    text = re.sub(r"[^a-z0-9]+", " ", str(value or "").casefold())
    return " ".join(text.split())


def token_set(value: Any) -> set[str]:
    return {
        token for token in normalize_text(value).split()
        if len(token) > 2 and token not in TOKEN_STOPWORDS
    }


def normalize_doi(value: Any) -> str:
    doi = str(value or "").strip().casefold()
    doi = re.sub(r"^(?:https?://(?:dx\.)?doi\.org/|doi:\s*)", "", doi)
    return doi.rstrip(". ")


def external_ids(paper: dict[str, Any]) -> dict[str, Any]:
    result = paper.get("externalIds") or paper.get("external_ids") or {}
    return result if isinstance(result, dict) else {}


def paper_doi(paper: dict[str, Any]) -> str:
    ids = external_ids(paper)
    for value in (ids.get("DOI"), ids.get("doi"), paper.get("doi")):
        doi = normalize_doi(value)
        if doi:
            return doi
    match = re.search(r"(?:doi\.org/|doi:)(10\.\d{4,9}/[^\s?#]+)", str(paper.get("url") or ""), re.I)
    return normalize_doi(match.group(1)) if match else ""


def paper_arxiv(paper: dict[str, Any]) -> str:
    ids = external_ids(paper)
    for value in (ids.get("ArXiv"), ids.get("arXiv"), paper.get("arxiv_id")):
        match = re.search(r"(?:arxiv:)?(\d{4}\.\d{4,5})(?:v\d+)?", str(value or ""), re.I)
        if match:
            return match.group(1).casefold()
    for value in (paper.get("paper_key"), paper.get("id"), paper.get("url")):
        match = re.search(r"(?<!\d)(\d{4}\.\d{4,5})(?:v\d+)?", str(value or ""), re.I)
        if match:
            return match.group(1).casefold()
    return ""


def identity_tokens(paper: dict[str, Any]) -> set[str]:
    result: set[str] = set()
    doi = paper_doi(paper)
    arxiv = paper_arxiv(paper)
    title = normalize_text(paper.get("title"))
    if doi:
        result.add(f"doi:{doi}")
    if arxiv:
        result.add(f"arxiv:{arxiv}")
    if title:
        result.add(f"title:{title}")
    return result


def authors(paper: dict[str, Any]) -> list[str]:
    raw = paper.get("authors") or []
    result = []
    for item in raw if isinstance(raw, list) else [raw]:
        if isinstance(item, dict):
            name = str(item.get("name") or "").strip()
        else:
            name = str(item or "").strip()
        if name:
            result.append(name)
    return result


def abstract(paper: dict[str, Any]) -> str:
    return str(paper.get("abstract") or paper.get("abs") or "").strip()


def metadata_score(paper: dict[str, Any]) -> tuple[int, int, int, int, int]:
    venue = paper.get("publication_venue") or paper.get("venue") or paper.get("journal")
    return (
        int(bool(paper_doi(paper))),
        int(bool(authors(paper))),
        int(bool(venue)),
        int(bool(paper.get("year") or paper.get("publicationDate"))),
        len(abstract(paper)),
    )


def list_union(*groups: Any) -> list[Any]:
    result = []
    seen = set()
    for group in groups:
        if not isinstance(group, list):
            continue
        for item in group:
            if item in (None, "", [], {}):
                continue
            marker = json.dumps(item, sort_keys=True, ensure_ascii=False) if isinstance(item, (dict, list)) else str(item)
            if marker not in seen:
                seen.add(marker)
                result.append(item)
    return result


def merge_group(group: list[dict[str, Any]]) -> tuple[dict[str, Any], dict[str, Any]]:
    ordered = sorted(group, key=metadata_score, reverse=True)
    merged = dict(ordered[0])
    conflicts: dict[str, Any] = {}
    dois = sorted({paper_doi(item) for item in group if paper_doi(item)})
    arxiv_ids = sorted({paper_arxiv(item) for item in group if paper_arxiv(item)})
    titles = sorted({str(item.get("title") or "").strip() for item in group if item.get("title")})
    if len(dois) > 1:
        conflicts["doi"] = dois
    if len(arxiv_ids) > 1:
        conflicts["arxiv"] = arxiv_ids
    if len(titles) > 1:
        conflicts["titles"] = titles
    for item in ordered[1:]:
        for key, value in item.items():
            if key in {"abstract", "abs"}:
                continue
            if merged.get(key) in (None, "", [], {}):
                merged[key] = value
    best_abstract = max((abstract(item) for item in group), key=len, default="")
    if best_abstract:
        merged["abstract"] = best_abstract
        merged["abs"] = best_abstract
    merged["authors"] = authors(ordered[0]) or max((authors(item) for item in group), key=len, default=[])
    merged["sources"] = list_union(
        *[item.get("sources") or [item.get("source")] for item in group]
    )
    merged["retrieval_routes"] = list_union(*[item.get("retrieval_routes") for item in group])
    merged["limitations"] = list_union(*[item.get("limitations") for item in group])
    merged["open_problem_candidates"] = list_union(
        *[item.get("open_problem_candidates") for item in group]
    )
    ids = dict(external_ids(merged))
    if dois:
        ids["DOI"] = dois[0]
    if arxiv_ids:
        ids["ArXiv"] = arxiv_ids[0]
    merged["externalIds"] = ids
    merged["canonical_identity_tokens"] = sorted(set().union(*(identity_tokens(item) for item in group)))
    merged["metadata_conflicts"] = conflicts
    return merged, conflicts


def merge_records(records: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    groups: list[list[dict[str, Any]]] = []
    owners: dict[str, int] = {}
    for record in records:
        if not record.get("title"):
            continue
        tokens = identity_tokens(record)
        matched = sorted({owners[token] for token in tokens if token in owners})
        if not matched:
            index = len(groups)
            groups.append([record])
        else:
            index = matched[0]
            groups[index].append(record)
            for other in reversed(matched[1:]):
                groups[index].extend(groups[other])
                groups[other] = []
                for token, owner in list(owners.items()):
                    if owner == other:
                        owners[token] = index
        for token in set().union(*(identity_tokens(item) for item in groups[index])):
            owners[token] = index
    merged = []
    conflicts = []
    for group in groups:
        if not group:
            continue
        paper, conflict = merge_group(group)
        if conflict:
            conflicts.append({"title": paper.get("title"), **conflict})
        merged.append(paper)
    merged.sort(key=lambda paper: (-(int(paper.get("year") or 0)), normalize_text(paper.get("title"))))
    assign_bib_keys(merged)
    return merged, conflicts


def surname(name: str) -> str:
    parts = re.findall(r"[A-Za-z0-9]+", name)
    return parts[-1].casefold() if parts else "paper"


def assign_bib_keys(records: list[dict[str, Any]]) -> None:
    used: set[str] = set()
    for paper in records:
        lead = surname(authors(paper)[0]) if authors(paper) else "paper"
        year = re.sub(r"\D", "", str(paper.get("year") or "nd")) or "nd"
        title_words = [token for token in token_set(paper.get("title")) if token not in TOKEN_STOPWORDS]
        stem = sorted(title_words, key=lambda token: normalize_text(paper.get("title")).find(token))[0] if title_words else "work"
        base = re.sub(r"[^a-z0-9]", "", f"{lead}{year}{stem}".casefold()) or "paper"
        key = base
        suffix = 2
        while key in used:
            key = f"{base}{suffix}"
            suffix += 1
        used.add(key)
        paper["bib_key"] = key


def state_load(path: Path) -> dict[str, Any]:
    return read_json(path) if path.exists() else {}


def state_event(state: dict[str, Any], kind: str, details: dict[str, Any]) -> None:
    state.setdefault("events", []).append(
        {"at": dt.datetime.now(dt.timezone.utc).isoformat(), "kind": kind, "details": details}
    )


def command_init(args: argparse.Namespace) -> int:
    state = {
        "schema_version": SCHEMA_VERSION,
        "topic": args.topic,
        "profile": args.profile,
        "cutoff_date": args.cutoff_date,
        "topic_signature": {
            "include_terms": args.include_term,
            "exclude_terms": args.exclude_term,
            "seed_papers": args.seed_paper,
        },
        "events": [],
    }
    state_event(state, "initialized", {"profile": args.profile})
    write_json(args.state, state)
    return 0


def flatten_paths(groups: list[list[Path]]) -> list[Path]:
    result = []
    for group in groups:
        result.extend(group)
    return result


def command_merge(args: argparse.Namespace) -> int:
    inputs = flatten_paths(args.input)
    records = [record for path in inputs for record in load_records(path)]
    merged, conflicts = merge_records(records)
    write_jsonl(args.registry, merged)
    report = {
        "schema_version": SCHEMA_VERSION,
        "inputs": [str(path) for path in inputs],
        "input_record_count": len(records),
        "canonical_record_count": len(merged),
        "merged_alias_count": len(records) - len(merged),
        "metadata_conflict_count": len(conflicts),
        "metadata_conflicts": conflicts,
    }
    write_json(args.report, report)
    return 0 if not conflicts else 2


def relevance_score(paper: dict[str, Any], query: str, includes: list[str], excludes: list[str]) -> tuple[float, list[str]]:
    title = normalize_text(paper.get("title"))
    body = normalize_text(" ".join([
        str(paper.get("title") or ""), abstract(paper),
        " ".join(map(str, paper.get("topics") or [])),
        str(paper.get("topic_category") or ""),
    ]))
    query_tokens = token_set(query)
    title_tokens = token_set(title)
    body_tokens = token_set(body)
    score = 0.0
    reasons = []
    if query_tokens:
        title_overlap = len(query_tokens & title_tokens) / len(query_tokens)
        body_overlap = len(query_tokens & body_tokens) / len(query_tokens)
        score += 5.0 * title_overlap + 2.0 * body_overlap
        reasons.append(f"query_title_overlap={title_overlap:.3f}")
        reasons.append(f"query_body_overlap={body_overlap:.3f}")
    include_hits = [term for term in includes if normalize_text(term) and normalize_text(term) in body]
    exclude_hits = [term for term in excludes if normalize_text(term) and normalize_text(term) in body]
    score += 1.5 * len(include_hits)
    score -= 5.0 * len(exclude_hits)
    if include_hits:
        reasons.append("include=" + ",".join(include_hits))
    if exclude_hits:
        reasons.append("exclude=" + ",".join(exclude_hits))
    score += 0.3 * int(bool(abstract(paper)))
    score += 0.2 * int(bool(paper_doi(paper) or paper_arxiv(paper)))
    score += 0.1 * int(bool(paper.get("venue") or paper.get("publication_venue")))
    return score, reasons


def compact_card(paper: dict[str, Any], score: float | None = None, reasons: list[str] | None = None, max_abstract_chars: int = 700) -> dict[str, Any]:
    card = {
        "id": paper.get("id") or paper.get("paperId") or paper.get("paper_key"),
        "bib_key": paper.get("bib_key"),
        "title": paper.get("title"),
        "authors": authors(paper),
        "year": paper.get("year"),
        "venue": paper.get("publication_venue") or paper.get("venue") or paper.get("journal"),
        "doi": paper_doi(paper) or None,
        "arxiv": paper_arxiv(paper) or None,
        "source": paper.get("sources") or paper.get("source"),
        "abstract": abstract(paper)[:max_abstract_chars],
        "topics": paper.get("topics") or ([paper.get("topic_category")] if paper.get("topic_category") else []),
        "evidence_status": paper.get("evidence_status"),
        "metadata_conflicts": paper.get("metadata_conflicts") or {},
    }
    if score is not None:
        card["relevance_score"] = round(score, 4)
        card["relevance_reasons"] = reasons or []
    return card


def command_shortlist(args: argparse.Namespace) -> int:
    records = load_records(args.registry)
    state = state_load(args.state) if args.state else {}
    signature = state.get("topic_signature") or {}
    includes = list(args.include_term or signature.get("include_terms") or [])
    excludes = list(args.exclude_term or signature.get("exclude_terms") or [])
    ranked = []
    for paper in records:
        score, reasons = relevance_score(paper, args.query, includes, excludes)
        if score >= args.min_score:
            ranked.append((score, paper, reasons))
    ranked.sort(key=lambda row: (-row[0], -(int(row[1].get("citationCount") or 0)), normalize_text(row[1].get("title"))))
    cards = [compact_card(paper, score, reasons, args.max_abstract_chars) for score, paper, reasons in ranked[: args.limit]]
    output = {"query": args.query, "pool_size": len(records), "returned": len(cards), "papers": cards}
    if args.output:
        write_json(args.output, output)
    else:
        print(json.dumps(output, indent=2, ensure_ascii=False))
    if args.state:
        state_event(state, "shortlist", {"query": args.query, "returned_ids": [card["id"] for card in cards]})
        write_json(args.state, state)
    return 0


def command_inspect(args: argparse.Namespace) -> int:
    records = load_records(args.registry)
    wanted = {
        candidate
        for value in args.id
        for candidate in (value.casefold(), normalize_text(value))
        if candidate
    }
    selected = []
    for paper in records:
        candidates = {
            str(paper.get("id") or "").casefold(),
            str(paper.get("paperId") or "").casefold(),
            str(paper.get("paper_key") or "").casefold(),
            str(paper.get("bib_key") or "").casefold(),
            paper_doi(paper), paper_arxiv(paper), normalize_text(paper.get("title")),
        }
        if candidates & wanted:
            card = compact_card(paper, max_abstract_chars=args.max_abstract_chars)
            card["limitations"] = paper.get("limitations") or []
            card["open_problem_candidates"] = paper.get("open_problem_candidates") or []
            card["retrieval_routes"] = paper.get("retrieval_routes") or []
            selected.append(card)
    output = {"requested": args.id, "matched": len(selected), "papers": selected}
    if args.output:
        write_json(args.output, output)
    else:
        print(json.dumps(output, indent=2, ensure_ascii=False))
    return 0 if selected else 2


def command_structure(args: argparse.Namespace) -> int:
    data = read_json(args.ledger)
    candidates = data.get("items") if isinstance(data, dict) else []
    accepted = []
    for item in candidates or []:
        kind = str(item.get("kind") or "")
        if args.kind != "all" and kind != args.kind:
            continue
        support = item.get("support_paper_keys") or []
        unresolved = item.get("unresolved_support_paper_ids") or []
        status = str(item.get("verification_status") or "")
        if not support or unresolved or "requires_claim_check" not in status:
            continue
        accepted.append({
            "id": item.get("id"), "kind": kind,
            "domain_id": item.get("domain_id"), "domain_title": item.get("domain_title"),
            "candidate_claim": item.get("candidate_claim"),
            "support_paper_keys": support,
            "verification_status": status,
            "allowed_use": "research_hypothesis_requiring_paper_check",
        })
    output = {"kind": args.kind, "returned": min(len(accepted), args.limit), "candidates": accepted[: args.limit]}
    if args.output:
        write_json(args.output, output)
    else:
        print(json.dumps(output, indent=2, ensure_ascii=False))
    return 0


def command_record(args: argparse.Namespace) -> int:
    state = state_load(args.state)
    details = json.loads(args.details) if args.details else {}
    state_event(state, args.kind, details)
    write_json(args.state, state)
    return 0


def tex_escape(value: Any) -> str:
    text = str(value or "")
    replacements = {"&": r"\&", "%": r"\%", "#": r"\#", "_": r"\_"}
    for old, new in replacements.items():
        text = text.replace(old, new)
    return text


def bib_entry(paper: dict[str, Any]) -> str:
    key = paper["bib_key"]
    fields = {
        "title": paper.get("title"),
        "author": " and ".join(authors(paper)),
        "year": paper.get("year"),
    }
    venue = paper.get("publication_venue") or paper.get("venue")
    journal = paper.get("journal")
    if isinstance(journal, dict):
        journal = journal.get("name")
    if journal:
        fields["journal"] = journal
        entry_type = "article"
    elif venue:
        fields["booktitle"] = venue
        entry_type = "inproceedings"
    else:
        fields["howpublished"] = "Preprint"
        entry_type = "misc"
    for name in ("volume", "issue", "pages", "publisher"):
        if paper.get(name):
            fields["number" if name == "issue" else name] = paper[name]
    doi = paper_doi(paper)
    arxiv = paper_arxiv(paper)
    if doi:
        fields["doi"] = doi
        fields["url"] = f"https://doi.org/{doi}"
    elif arxiv:
        fields["eprint"] = arxiv
        fields["archivePrefix"] = "arXiv"
        fields["url"] = f"https://arxiv.org/abs/{arxiv}"
    lines = [f"@{entry_type}{{{key},"]
    for name, value in fields.items():
        if value not in (None, "", []):
            lines.append(f"  {name} = {{{tex_escape(value)}}},")
    lines.append("}")
    return "\n".join(lines)


def command_bibtex(args: argparse.Namespace) -> int:
    records = load_records(args.registry)
    if any(not paper.get("bib_key") for paper in records):
        assign_bib_keys(records)
        write_jsonl(args.registry, records)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text("\n\n".join(bib_entry(paper) for paper in records) + "\n", encoding="utf-8")
    return 0


def fetch_crossref(doi: str, timeout: float = 20.0) -> dict[str, Any]:
    url = "https://api.crossref.org/works/" + urllib.parse.quote(doi, safe="")
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": "ReasFlow-CodexFirstSurvey/1.0",
        },
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        payload = json.loads(response.read().decode("utf-8"))
    message = payload.get("message") if isinstance(payload, dict) else None
    return message if isinstance(message, dict) else {}


def crossref_year(message: dict[str, Any]) -> int | None:
    for name in ("published-print", "published-online", "issued", "created"):
        value = message.get(name)
        if not isinstance(value, dict):
            continue
        parts = value.get("date-parts")
        if isinstance(parts, list) and parts and isinstance(parts[0], list) and parts[0]:
            try:
                return int(parts[0][0])
            except (TypeError, ValueError):
                pass
    return None


def title_similarity(left: Any, right: Any) -> float:
    left_tokens = token_set(left)
    right_tokens = token_set(right)
    if not left_tokens or not right_tokens:
        return 0.0
    return len(left_tokens & right_tokens) / len(left_tokens | right_tokens)


def crossref_authors(message: dict[str, Any]) -> list[str]:
    result = []
    for item in message.get("author") or []:
        if not isinstance(item, dict):
            continue
        name = " ".join(
            part for part in (str(item.get("given") or "").strip(), str(item.get("family") or "").strip())
            if part
        )
        if name:
            result.append(name)
    return result


def command_validate_doi(args: argparse.Namespace) -> int:
    records = load_records(args.registry)
    cited_from = getattr(args, "cited_from", [])
    if cited_from:
        cited = set()
        for path in cited_from:
            cited.update(cite_keys(path.read_text(encoding="utf-8")))
        records = [paper for paper in records if str(paper.get("bib_key") or "") in cited]
    audit: list[dict[str, Any]] = []
    for paper in records:
        doi = paper_doi(paper)
        if not doi:
            continue
        item: dict[str, Any] = {"bib_key": paper.get("bib_key"), "doi": doi}
        try:
            message = fetch_crossref(doi, args.timeout)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            item.update({"status": "unavailable", "error": type(exc).__name__})
            audit.append(item)
            continue
        titles = message.get("title") or []
        crossref_title = str(titles[0] if isinstance(titles, list) and titles else titles or "").strip()
        similarity = title_similarity(paper.get("title"), crossref_title)
        item.update({"crossref_title": crossref_title, "title_similarity": round(similarity, 4)})
        if similarity < args.min_title_similarity:
            ids = dict(external_ids(paper))
            ids.pop("DOI", None)
            ids.pop("doi", None)
            paper["externalIds"] = ids
            if "doi.org" in str(paper.get("url") or ""):
                paper["url"] = f"https://arxiv.org/abs/{paper_arxiv(paper)}" if paper_arxiv(paper) else ""
            paper.setdefault("rejected_identifiers", []).append(
                {"type": "DOI", "value": doi, "reason": "crossref_title_mismatch", "crossref_title": crossref_title}
            )
            item["status"] = "rejected_title_mismatch"
            audit.append(item)
            continue
        paper["title"] = crossref_title or paper.get("title")
        if crossref_authors(message):
            paper["authors"] = crossref_authors(message)
        if crossref_year(message):
            paper["year"] = crossref_year(message)
        containers = message.get("container-title") or []
        venue = str(containers[0] if isinstance(containers, list) and containers else containers or "").strip()
        if venue:
            paper["venue"] = venue
            paper["publication_venue"] = venue
        for target, source in (("volume", "volume"), ("issue", "issue"), ("pages", "page"), ("publisher", "publisher")):
            if message.get(source):
                paper[target] = message[source]
        paper["doi_validation"] = {
            "status": "validated_crossref", "title_similarity": round(similarity, 4)
        }
        item["status"] = "validated"
        audit.append(item)
    # TeX manuscripts already refer to the registry keys.  Crossref may improve
    # display metadata, but validation must never rename those stable keys.
    write_jsonl(args.output_registry, records)
    report = {
        "schema_version": SCHEMA_VERSION,
        "checked": len(audit),
        "validated": sum(item["status"] == "validated" for item in audit),
        "rejected": sum(item["status"] == "rejected_title_mismatch" for item in audit),
        "unavailable": sum(item["status"] == "unavailable" for item in audit),
        "items": audit,
    }
    write_json(args.report, report)
    return 2 if report["rejected"] else 0


def cite_keys(tex: str) -> set[str]:
    result = set()
    for match in re.finditer(r"\\cite(?:t|p|alp|author|year|yearpar)?\s*(?:\[[^]]*\]\s*){0,2}\{([^}]+)\}", tex):
        result.update(key.strip() for key in match.group(1).split(",") if key.strip())
    return result


def bib_keys(text: str) -> set[str]:
    return set(re.findall(r"@\w+\s*\{\s*([^,\s]+)", text))


def command_audit(args: argparse.Namespace) -> int:
    state = state_load(args.state)
    records = load_records(args.registry)
    survey_text = args.survey.read_text(encoding="utf-8") if args.survey.exists() else ""
    related_text = args.related.read_text(encoding="utf-8") if args.related.exists() else ""
    bib_text = args.bib.read_text(encoding="utf-8") if args.bib.exists() else ""
    survey_cites = cite_keys(survey_text)
    related_cites = cite_keys(related_text)
    bibliography = bib_keys(bib_text)
    token_owners: dict[str, list[str]] = {}
    for paper in records:
        for token in identity_tokens(paper):
            token_owners.setdefault(token, []).append(str(paper.get("bib_key") or paper.get("title")))
    duplicates = {token: owners for token, owners in token_owners.items() if len(owners) > 1}
    missing_metadata = []
    conflicts = []
    for paper in records:
        missing = [name for name, value in {
            "title": paper.get("title"), "authors": authors(paper), "year": paper.get("year")
        }.items() if not value]
        if missing:
            missing_metadata.append({"bib_key": paper.get("bib_key"), "missing": missing})
        if paper.get("metadata_conflicts"):
            conflicts.append({"bib_key": paper.get("bib_key"), "conflicts": paper["metadata_conflicts"]})
    report = {
        "schema_version": SCHEMA_VERSION,
        "topic": state.get("topic"), "profile": state.get("profile"),
        "state_sha256": hashlib.sha256(args.state.read_bytes()).hexdigest() if args.state.exists() else None,
        "registry_record_count": len(records),
        "survey_distinct_citations": len(survey_cites),
        "related_works_distinct_citations": len(related_cites),
        "survey_missing_bib_keys": sorted(survey_cites - bibliography),
        "related_works_missing_bib_keys": sorted(related_cites - bibliography),
        "canonical_duplicate_count": len(duplicates),
        "canonical_duplicates": duplicates,
        "metadata_conflict_count": len(conflicts),
        "metadata_conflicts": conflicts,
        "minimum_metadata_failure_count": len(missing_metadata),
        "minimum_metadata_failures": missing_metadata,
        "gates": {
            "survey_100_plus": len(survey_cites) >= 100,
            "related_works_45_to_55": 45 <= len(related_cites) <= 55,
            "all_citation_keys_resolve": not ((survey_cites | related_cites) - bibliography),
            "canonical_unique": not duplicates,
            "minimum_metadata_present": not missing_metadata,
        },
        "limitations": [
            "This deterministic audit does not establish claim-citation entailment.",
            "Venue and DOI correctness require source-level metadata validation.",
        ],
    }
    report["gate_passed"] = all(report["gates"].values())
    write_json(args.output, report)
    return 0 if report["gate_passed"] else 2


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description=__doc__)
    commands = root.add_subparsers(dest="command", required=True)

    command = commands.add_parser("init")
    command.add_argument("--topic", required=True)
    command.add_argument("--profile", choices=("reascholar-s2", "s2-only"), required=True)
    command.add_argument("--cutoff-date", default="")
    command.add_argument("--include-term", action="append", default=[])
    command.add_argument("--exclude-term", action="append", default=[])
    command.add_argument("--seed-paper", action="append", default=[])
    command.add_argument("--state", type=Path, required=True)
    command.set_defaults(handler=command_init)

    command = commands.add_parser("merge")
    command.add_argument("--input", type=Path, nargs="+", action="append", required=True)
    command.add_argument("--registry", type=Path, required=True)
    command.add_argument("--report", type=Path, required=True)
    command.add_argument(
        "--cited-from",
        type=Path,
        action="append",
        default=[],
        help="Validate only records cited by one or more TeX manuscripts.",
    )
    command.set_defaults(handler=command_merge)

    command = commands.add_parser("shortlist")
    command.add_argument("--registry", type=Path, required=True)
    command.add_argument("--state", type=Path)
    command.add_argument("--query", required=True)
    command.add_argument("--include-term", action="append")
    command.add_argument("--exclude-term", action="append")
    command.add_argument("--limit", type=int, default=15)
    command.add_argument("--min-score", type=float, default=0.5)
    command.add_argument("--max-abstract-chars", type=int, default=700)
    command.add_argument("--output", type=Path)
    command.set_defaults(handler=command_shortlist)

    command = commands.add_parser("inspect")
    command.add_argument("--registry", type=Path, required=True)
    command.add_argument("--id", action="append", required=True)
    command.add_argument("--max-abstract-chars", type=int, default=3000)
    command.add_argument("--output", type=Path)
    command.set_defaults(handler=command_inspect)

    command = commands.add_parser("structure")
    command.add_argument("--ledger", type=Path, required=True)
    command.add_argument("--kind", choices=("timeline", "limitation", "gap", "future_work", "all"), default="all")
    command.add_argument("--limit", type=int, default=12)
    command.add_argument("--output", type=Path)
    command.set_defaults(handler=command_structure)

    command = commands.add_parser("record")
    command.add_argument("--state", type=Path, required=True)
    command.add_argument("--kind", required=True)
    command.add_argument("--details", default="{}")
    command.set_defaults(handler=command_record)

    command = commands.add_parser("bibtex")
    command.add_argument("--registry", type=Path, required=True)
    command.add_argument("--output", type=Path, required=True)
    command.set_defaults(handler=command_bibtex)

    command = commands.add_parser("validate-doi")
    command.add_argument("--registry", type=Path, required=True)
    command.add_argument("--output-registry", type=Path, required=True)
    command.add_argument("--report", type=Path, required=True)
    command.add_argument("--min-title-similarity", type=float, default=0.65)
    command.add_argument("--timeout", type=float, default=20.0)
    command.set_defaults(handler=command_validate_doi)

    command = commands.add_parser("audit")
    command.add_argument("--state", type=Path, required=True)
    command.add_argument("--registry", type=Path, required=True)
    command.add_argument("--survey", type=Path, required=True)
    command.add_argument("--related", type=Path, required=True)
    command.add_argument("--bib", type=Path, required=True)
    command.add_argument("--output", type=Path, required=True)
    command.set_defaults(handler=command_audit)
    return root


def main() -> int:
    args = parser().parse_args()
    return int(args.handler(args))


if __name__ == "__main__":
    sys.exit(main())
