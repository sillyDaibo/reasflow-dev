#!/usr/bin/env python3
"""Build additive ReaScholar+S2 and S2-only survey retrieval artifacts."""

from __future__ import annotations

import argparse
import contextlib
import fcntl
import hashlib
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable

SURVEY_SKILL_ROOT = Path(__file__).resolve().parents[2]
if str(SURVEY_SKILL_ROOT) not in sys.path:
    sys.path.insert(0, str(SURVEY_SKILL_ROOT))

from workspace_env import load_workspace_survey_env

load_workspace_survey_env()


REASCHOLAR_BASE = os.getenv("REASCHOLAR_BASE_URL", "https://scholar.reaslab.io").rstrip(
    "/"
)
S2_BASE = "https://api.semanticscholar.org/graph/v1"
USER_AGENT = "ReasFlow-ReaScholar-TwoStage/1.0"
TIMEOUT = 45
RETRIES = 6
S2_MIN_INTERVAL_SECONDS = float(os.getenv("S2_MIN_INTERVAL_SECONDS", "1.1"))
S2_RATE_LOCK_PATH = "/tmp/reasflow-semantic-scholar-rate.lock"
S2_FIELDS = (
    "paperId,title,authors,year,abstract,citationCount,referenceCount,url,"
    "externalIds,venue,publicationDate,publicationTypes,journal"
)
PROFILES = {"reascholar-s2", "s2-only"}
QUERY_TEMPLATES = (
    "{topic}",
    "{topic} algorithms",
    "{topic} convergence",
    "{topic} survey",
)
GENERIC_TOPIC_WORDS = {
    "and",
    "comparative",
    "evolution",
    "for",
    "foundations",
    "in",
    "mechanisms",
    "methods",
    "of",
    "over",
    "the",
}
STOPWORDS = {
    "about",
    "across",
    "after",
    "and",
    "among",
    "based",
    "efficient",
    "for",
    "from",
    "into",
    "methods",
    "optimization",
    "over",
    "research",
    "theory",
    "under",
    "using",
    "with",
}
GENERIC_SUPPORT_WORDS = {
    "algorithm",
    "algorithms",
    "analysis",
    "approach",
    "information",
    "method",
    "problem",
    "problems",
    "system",
    "systems",
}
GENERIC_CITATION_WORDS = GENERIC_SUPPORT_WORDS | {
    "complexity",
    "convergence",
    "error",
    "rate",
    "stochastic",
}
GENERIC_DOMAIN_WORDS = GENERIC_CITATION_WORDS | {
    "averaging",
    "constraint",
    "constrained",
    "convex",
    "converg",
    "deterministic",
    "gradient",
    "guarantee",
    "momentum",
    "oracle",
    "smooth",
    "synchronous",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def api_key() -> str:
    return (
        os.getenv("SEMANTIC_SCHOLAR_API_KEY", "").strip()
        or os.getenv("S2_API_KEY", "").strip()
    )


@contextlib.contextmanager
def semantic_scholar_rate_slot():
    """Serialize S2 calls from paired arms without persisting credentials."""
    with open(S2_RATE_LOCK_PATH, "a+", encoding="utf-8") as lock_handle:
        fcntl.flock(lock_handle.fileno(), fcntl.LOCK_EX)
        try:
            time.sleep(max(0.0, S2_MIN_INTERVAL_SECONDS))
            yield
        finally:
            fcntl.flock(lock_handle.fileno(), fcntl.LOCK_UN)


def request_json(
    base: str,
    path: str,
    *,
    payload: dict[str, Any] | None = None,
    params: dict[str, Any] | None = None,
    s2: bool = False,
) -> dict[str, Any]:
    filtered = {k: v for k, v in (params or {}).items() if v not in (None, "")}
    url = f"{base}{path}"
    if filtered:
        url += "?" + urllib.parse.urlencode(filtered, doseq=True)
    headers = {"Accept": "application/json", "User-Agent": USER_AGENT}
    if s2 and api_key():
        headers["x-api-key"] = api_key()
    body = None
    method = "GET"
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
        method = "POST"
    for attempt in range(RETRIES):
        req = urllib.request.Request(url, data=body, headers=headers, method=method)
        try:
            request_slot = semantic_scholar_rate_slot() if s2 else contextlib.nullcontext()
            with request_slot:
                with urllib.request.urlopen(req, timeout=TIMEOUT) as response:
                    return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            error_body = exc.read().decode("utf-8", errors="replace")
            if exc.code in {429, 500, 502, 503, 504} and attempt + 1 < RETRIES:
                retry_after = exc.headers.get("Retry-After", "")
                delay = (
                    float(retry_after)
                    if retry_after.replace(".", "", 1).isdigit()
                    else 2**attempt
                )
                time.sleep(delay)
                continue
            raise RuntimeError(
                f"HTTP {exc.code} from {url}: {error_body[:300]}"
            ) from exc
        except urllib.error.URLError as exc:
            if attempt + 1 < RETRIES:
                time.sleep(2**attempt)
                continue
            raise RuntimeError(f"Network error from {url}: {exc}") from exc
    raise RuntimeError(f"Request failed after retries: {url}")


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def token_set(value: str) -> set[str]:
    return {
        token
        for token in re.findall(r"[a-z0-9]+", value.casefold())
        if len(token) >= 3 and token not in STOPWORDS
    }


def match_token_set(value: str) -> set[str]:
    """Normalize a few common scientific morphology variants for matching."""

    normalized: set[str] = set()
    for token in token_set(value):
        for prefix in (
            "communicat",
            "converg",
            "inequalit",
            "quantiz",
            "robust",
        ):
            if token.startswith(prefix):
                token = prefix
                break
        normalized.add(token)
    return normalized


def paper_key_from(value: dict[str, Any]) -> str:
    return str(value.get("paper_key") or value.get("paperKey") or "").strip()


def frozen_paper_key(value: dict[str, Any]) -> str:
    key = paper_key_from(value)
    if key:
        return key
    paper_id = str(value.get("paperId") or "").strip()
    return str(value.get("id") or (f"s2:{paper_id}" if paper_id else "")).strip()


def arxiv_from_key(value: str) -> str:
    match = re.match(r"^(\d{4}\.\d{4,5})(?:v\d+)?(?:__|$)", value)
    return match.group(1) if match else ""


def clean_authors(value: Any) -> list[str]:
    if isinstance(value, str):
        return [item.strip() for item in re.split(r";|\band\b", value) if item.strip()]
    if not isinstance(value, list):
        return []
    authors: list[str] = []
    for item in value:
        name = (
            str(item.get("name") or "").strip()
            if isinstance(item, dict)
            else str(item).strip()
        )
        if name:
            authors.append(name)
    return authors


def first_text(*values: Any) -> str:
    for value in values:
        if value is not None and str(value).strip():
            return str(value).strip()
    return ""


def normalize_s2(item: dict[str, Any], route: str) -> dict[str, Any]:
    external = (
        item.get("externalIds") if isinstance(item.get("externalIds"), dict) else {}
    )
    paper_id = str(item.get("paperId") or "")
    journal = item.get("journal") if isinstance(item.get("journal"), dict) else {}
    return {
        "id": f"s2:{paper_id}" if paper_id else "",
        "paperId": paper_id,
        "paper_key": "",
        "title": str(item.get("title") or "").strip(),
        "authors": clean_authors(item.get("authors")),
        "year": item.get("year"),
        "venue": str(item.get("venue") or ""),
        "publication_venue": str(item.get("venue") or journal.get("name") or ""),
        "publication_types": item.get("publicationTypes") or [],
        "journal": journal,
        "volume": str(journal.get("volume") or ""),
        "pages": str(journal.get("pages") or ""),
        "abstract": str(item.get("abstract") or ""),
        "abs": str(item.get("abstract") or ""),
        "citationCount": int(item.get("citationCount") or 0),
        "referenceCount": int(item.get("referenceCount") or 0),
        "url": str(item.get("url") or ""),
        "externalIds": external,
        "publicationDate": str(item.get("publicationDate") or ""),
        "source": "semantic_scholar",
        "sources": ["semantic_scholar"],
        "retrieval_routes": [route],
        "evidence_status": "metadata_only_pending_primary_verification",
    }


def normalize_reascholar(
    item: dict[str, Any], detail: dict[str, Any] | None, route: str
) -> dict[str, Any]:
    detail = detail or {}
    display = detail.get("display") if isinstance(detail.get("display"), dict) else {}
    overview = (
        display.get("overview") if isinstance(display.get("overview"), dict) else {}
    )
    publication = (
        overview.get("publication")
        if isinstance(overview.get("publication"), dict)
        else {}
    )
    classification = (
        overview.get("classification")
        if isinstance(overview.get("classification"), dict)
        else {}
    )
    domain = item.get("domain") if isinstance(item.get("domain"), dict) else {}
    key = paper_key_from(item) or paper_key_from(detail)
    arxiv_id = arxiv_from_key(key)
    doi = first_text(item.get("doi"), publication.get("doi"))
    external: dict[str, str] = {}
    if arxiv_id:
        external["ArXiv"] = arxiv_id
    if doi.startswith("10."):
        external["DOI"] = doi
    title = first_text(item.get("title"), detail.get("title"))
    profile = first_text(
        overview.get("profile"), item.get("profile"), item.get("summary_markdown")
    )
    domain_name = first_text(
        domain.get("l2_name_en"),
        classification.get("l2_name_en"),
        domain.get("l1_name_en"),
        classification.get("l1_name_en"),
        item.get("category"),
    )
    url = (
        f"https://arxiv.org/abs/{arxiv_id}"
        if arxiv_id
        else (f"https://doi.org/{doi}" if doi else "")
    )
    links = item.get("links") if isinstance(item.get("links"), dict) else {}
    experiment = (
        display.get("experiment")
        if isinstance(display.get("experiment"), dict)
        else {}
    )
    limitation_candidates = experiment.get("limitations") or []
    if not isinstance(limitation_candidates, list):
        limitation_candidates = [limitation_candidates]
    limitation_candidates = [
        str(value).strip()
        for value in limitation_candidates
        if str(value).strip()
    ]
    return {
        "id": f"reascholar:{key}" if key else "",
        "paperId": f"reascholar:{key}" if key else "",
        "paper_key": key,
        "title": title,
        "authors": clean_authors(item.get("authors") or publication.get("authors")),
        "year": item.get("year") or publication.get("year"),
        "venue": first_text(publication.get("venue")),
        "publication_venue": first_text(publication.get("venue")),
        "publication_types": [],
        "journal": {},
        "volume": first_text(publication.get("volume")),
        "issue": first_text(publication.get("issue")),
        "pages": first_text(publication.get("pages")),
        "publisher": first_text(publication.get("publisher")),
        "topic_category": domain_name,
        "abstract": profile,
        "abs": profile,
        "citationCount": int(item.get("citationCount") or 0),
        "referenceCount": int(item.get("referenceCount") or 0),
        "url": url,
        "externalIds": external,
        "publicationDate": "",
        "raw_bibtex": str(publication.get("bibtex") or ""),
        "source": "reascholar",
        "sources": ["reascholar"],
        "retrieval_routes": [route],
        "support_domain_id": item.get("support_domain_id"),
        "summary_markdown": first_text(
            item.get("summary_markdown"), detail.get("summary_markdown")
        ),
        "limitations": limitation_candidates,
        # Candidates must be checked against later work before being described
        # as unresolved at the survey cutoff.
        "open_problem_candidates": limitation_candidates,
        "topics": [domain_name] if domain_name else [],
        "links": links,
        "evidence_status": "structured_detail_retrieved"
        if detail
        else "metadata_only_pending_primary_verification",
    }


def identity(paper: dict[str, Any]) -> str:
    external = (
        paper.get("externalIds") if isinstance(paper.get("externalIds"), dict) else {}
    )
    if external.get("DOI"):
        return "doi:" + str(external["DOI"]).casefold()
    if external.get("ArXiv"):
        return "arxiv:" + re.sub(r"v\d+$", "", str(external["ArXiv"]).casefold())
    title = re.sub(r"[^a-z0-9]+", " ", str(paper.get("title") or "").casefold()).strip()
    return f"title:{title}|{paper.get('year') or ''}"


def identity_tokens(paper: dict[str, Any]) -> set[str]:
    """Return all usable identities so cross-provider matches merge transitively."""
    external = (
        paper.get("externalIds") if isinstance(paper.get("externalIds"), dict) else {}
    )
    tokens: set[str] = set()
    doi = first_text(external.get("DOI"), paper.get("doi")).casefold()
    doi = re.sub(r"^https?://(?:dx\.)?doi\.org/", "", doi).strip()
    if doi.startswith("10."):
        tokens.add(f"doi:{doi}")
    arxiv = first_text(external.get("ArXiv"), external.get("arXiv"))
    arxiv = re.sub(r"v\d+$", "", arxiv.casefold()).strip()
    if arxiv:
        tokens.add(f"arxiv:{arxiv}")
    paper_key = paper_key_from(paper)
    if paper_key:
        tokens.add(f"reascholar:{paper_key.casefold()}")
        key_arxiv = arxiv_from_key(paper_key)
        if key_arxiv:
            tokens.add(f"arxiv:{key_arxiv.casefold()}")
    title = normalized_title(str(paper.get("title") or ""))
    if title:
        tokens.add(f"title:{title}")
    paper_id = str(paper.get("paperId") or "").strip()
    if paper_id and not paper_id.startswith("reascholar:"):
        tokens.add(f"s2:{paper_id}")
    return tokens


def _merge_into(target: dict[str, Any], paper: dict[str, Any]) -> None:
    for field in (
        "authors",
        "year",
        "venue",
        "publication_venue",
        "publication_types",
        "journal",
        "volume",
        "issue",
        "pages",
        "publisher",
        "topic_category",
        "abstract",
        "abs",
        "url",
        "publicationDate",
        "raw_bibtex",
        "paper_key",
    ):
        if not target.get(field) and paper.get(field):
            target[field] = paper[field]
    for field in ("citationCount", "referenceCount"):
        target[field] = max(int(target.get(field) or 0), int(paper.get(field) or 0))
    target["externalIds"] = {
        **(paper.get("externalIds") or {}),
        **(target.get("externalIds") or {}),
    }
    for field in ("sources", "retrieval_routes", "topics"):
        target[field] = list(
            dict.fromkeys([*(target.get(field) or []), *(paper.get(field) or [])])
        )
    for field in ("limitations", "open_problem_candidates"):
        target[field] = list(
            dict.fromkeys([*(target.get(field) or []), *(paper.get(field) or [])])
        )
    target["source"] = "+".join(target.get("sources") or [])
    if paper.get("evidence_status") == "structured_detail_retrieved":
        target["evidence_status"] = "structured_detail_retrieved"


def merge_papers(papers: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = [dict(paper) for paper in papers if paper.get("title")]
    parent = list(range(len(rows)))

    def find(index: int) -> int:
        while parent[index] != index:
            parent[index] = parent[parent[index]]
            index = parent[index]
        return index

    token_owner: dict[str, int] = {}
    for index, paper in enumerate(rows):
        for token in identity_tokens(paper):
            owner = token_owner.get(token)
            if owner is None:
                token_owner[token] = index
                continue
            left, right = find(index), find(owner)
            if left != right:
                parent[right] = left

    clusters: dict[int, list[int]] = {}
    for index in range(len(rows)):
        clusters.setdefault(find(index), []).append(index)
    merged: list[dict[str, Any]] = []
    for members in sorted(clusters.values(), key=min):
        target = dict(rows[members[0]])
        for index in members[1:]:
            _merge_into(target, rows[index])
        target["canonical_identity_tokens"] = sorted(
            set().union(*(identity_tokens(rows[index]) for index in members))
        )
        merged.append(target)
    return merged


def duplicate_identity_tokens(papers: list[dict[str, Any]]) -> dict[str, list[int]]:
    owners: dict[str, list[int]] = {}
    for index, paper in enumerate(papers):
        for token in identity_tokens(paper):
            owners.setdefault(token, []).append(index)
    return {token: indexes for token, indexes in owners.items() if len(indexes) > 1}


def discover_domains(topic: str, args: argparse.Namespace) -> dict[str, Any]:
    return request_json(
        REASCHOLAR_BASE,
        "/api/search/domains",
        payload={
            "query": topic,
            "top_k": args.discovery_count,
            "search_depth": args.search_depth,
            "anchor_paper_count": args.anchor_papers,
        },
    )


def domain_selection_score(domain: dict[str, Any], topic_tokens: set[str]) -> float:
    anchors = " ".join(
        str(item.get("title") or "") for item in domain.get("anchor_papers", [])
    )
    text = (
        " ".join(
            str(domain.get(field) or "")
            for field in ("title", "description", "l1_title")
        )
        + " "
        + anchors
    )
    overlap = len(topic_tokens & match_token_set(text)) / max(1, len(topic_tokens))
    breakdown = (
        domain.get("score_breakdown")
        if isinstance(domain.get("score_breakdown"), dict)
        else {}
    )
    topic_relevance = float(
        breakdown.get("topic_relevance") or domain.get("score") or 0.0
    )
    lexical_match = float(breakdown.get("lexical_match_score") or 0.0)
    title_tokens = match_token_set(str(domain.get("title") or ""))
    direct_title_overlap = len(topic_tokens & title_tokens)
    specific_title_tokens = title_tokens - GENERIC_DOMAIN_WORDS
    specific_title_overlap = len(topic_tokens & specific_title_tokens) / max(
        1, len(specific_title_tokens)
    )
    topic_lead = next(iter(match_token_set(str(domain.get("_topic_lead") or ""))), "")
    lead_match = float(bool(topic_lead and topic_lead in title_tokens))
    return round(
        0.28 * topic_relevance
        + 0.18 * lexical_match
        + 0.14 * overlap
        + 0.25 * specific_title_overlap
        + 0.10 * lead_match
        + 0.025 * min(direct_title_overlap, 2),
        6,
    )


def select_domains(
    discovery: dict[str, Any], topic: str, args: argparse.Namespace
) -> list[dict[str, Any]]:
    candidates = [
        item for item in discovery.get("domains", []) if isinstance(item, dict)
    ]
    requested_ids = list(dict.fromkeys(int(value) for value in args.domain_id))
    requested = set(requested_ids)
    if requested_ids:
        selected_by_id = {
            int(item.get("domain_id", -1)): item
            for item in candidates
            if int(item.get("domain_id", -1)) in requested
        }
        selected = [
            selected_by_id[domain_id]
            for domain_id in requested_ids
            if domain_id in selected_by_id
        ]
        missing = sorted(
            requested - {int(item.get("domain_id", -1)) for item in selected}
        )
        if missing:
            # A semantic top-k response can omit a known local taxonomy label
            # (for example, ``Quantized`` for a quantization-focused task).
            # Resolve explicit IDs against the same ReaScholar instance so the
            # caller can use the frozen local taxonomy without borrowing IDs
            # from another snapshot.  The details endpoint is still provenance
            # checked and the selected IDs are retained in the manifest.
            for domain_id in missing:
                detail = request_json(REASCHOLAR_BASE, f"/api/search/domains/{domain_id}")
                domain = detail.get("domain") if isinstance(detail, dict) else None
                if not isinstance(domain, dict):
                    # Search-domain detail responses expose the L2 fields at
                    # the top level; normalize that shape for the scaffold.
                    domain = detail if isinstance(detail, dict) and detail.get("domain_id") is not None else None
                if not isinstance(domain, dict):
                    raise RuntimeError(f"Requested Domain ID unavailable from local ReaScholar: {domain_id}")
                display = detail.get("display") if isinstance(detail.get("display"), dict) else {}
                overview = display.get("overview") if isinstance(display.get("overview"), dict) else {}
                selected.append({
                    "domain_id": domain_id,
                    "title": domain.get("title") or domain.get("label") or domain.get("l2_name_en") or f"Domain {domain_id}",
                    "description": overview.get("core_topic") or domain.get("l2_core_topic") or domain.get("description"),
                    "paper_count": detail.get("paper_count"),
                    "score": None,
                    "score_breakdown": {"selection": "explicit_local_domain_id"},
                    "anchor_papers": (detail.get("top_papers") or overview.get("support_papers") or [])[: args.anchor_papers],
                })
        selected_by_id = {int(item["domain_id"]): item for item in selected}
        return [selected_by_id[domain_id] for domain_id in requested_ids]
    topic_tokens = match_token_set(topic)
    topic_lead = next(iter(re.findall(r"[a-z0-9]+", topic.casefold())), "")
    for item in candidates:
        item["_topic_lead"] = topic_lead
        item["client_selection_score"] = domain_selection_score(item, topic_tokens)
        title_tokens = match_token_set(str(item.get("title") or ""))
        title_overlap = len(topic_tokens & title_tokens)
        specific_title_overlap = len(
            topic_tokens & (title_tokens - GENERIC_DOMAIN_WORDS)
        )
        breakdown = item.get("score_breakdown") or {}
        item["client_direct_title_overlap"] = title_overlap
        item["client_specific_title_overlap"] = specific_title_overlap
        item["client_lexical_match_score"] = float(
            breakdown.get("lexical_match_score") or 0.0
        )
        item.pop("_topic_lead", None)
    ranked = sorted(
        candidates,
        key=lambda item: (
            float(item.get("client_selection_score") or 0),
            float(item.get("score") or 0),
        ),
        reverse=True,
    )
    if not ranked:
        return []
    specific = [
        item for item in ranked if item["client_specific_title_overlap"] > 0
    ]
    if specific:
        selected = specific
    else:
        best_score = float(ranked[0].get("client_selection_score") or 0.0)
        selected = [
            item
            for item in ranked
            if item["client_lexical_match_score"] >= 0.5
            or (
                item["client_direct_title_overlap"] > 0
                and float(item.get("client_selection_score") or 0.0)
                >= 0.8 * best_score
            )
        ]
    # A topic can map cleanly to one L2. Treat domain_count as a cap instead of
    # padding the treatment with broad neighboring domains.
    return (selected or ranked[:1])[: args.domain_count]


def fetch_domain_details(selected: list[dict[str, Any]]) -> list[dict[str, Any]]:
    details: list[dict[str, Any]] = []
    for domain in selected:
        domain_id = int(domain["domain_id"])
        details.append(
            request_json(REASCHOLAR_BASE, f"/api/search/domains/{domain_id}")
        )
    return details


def narrative_claim(kind: str, item: dict[str, Any]) -> str:
    fields = {
        "timeline": ("title", "description"),
        "limitation": ("name", "description"),
        "future_work": ("direction", "description", "why_now", "first_step"),
    }[kind]
    return " — ".join(
        first_text(item.get(field)) for field in fields if first_text(item.get(field))
    )


def build_domain_scaffold(
    details: list[dict[str, Any]],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    domains: list[dict[str, Any]] = []
    ledger: list[dict[str, Any]] = []
    support_papers: list[dict[str, Any]] = []
    seen_narratives: set[tuple[int, str, str, tuple[str, ...]]] = set()
    for detail in details:
        display = (
            detail.get("display") if isinstance(detail.get("display"), dict) else {}
        )
        domain_id = int(detail.get("domain_id"))
        domains.append(
            {
                "domain_id": domain_id,
                "title": detail.get("title"),
                "l1_domain_id": detail.get("l1_domain_id"),
                "l1_name_en": detail.get("l1_name_en"),
                "paper_count": detail.get("paper_count"),
                "overview": display.get("overview", {}),
                "provenance": display.get("provenance", {}),
            }
        )
        for api_kind, output_kind in (
            ("timeline", "timeline"),
            ("limitations", "limitation"),
            ("future_works", "future_work"),
        ):
            for index, item in enumerate(display.get(api_kind, []) or []):
                if not isinstance(item, dict):
                    continue
                mapped = [
                    paper
                    for paper in item.get("support_papers") or []
                    if isinstance(paper, dict) and paper_key_from(paper)
                ]
                support_papers.extend(
                    {
                        **paper,
                        "support_domain_id": domain_id,
                        "support_kind": "domain_narrative_support",
                    }
                    for paper in mapped
                )
                unresolved = [
                    str(value)
                    for value in item.get("unresolved_support_paper_ids") or []
                ]
                claim = narrative_claim(output_kind, item)
                # Only a synthesized direction with an explicit motivation and
                # actionable first step is eligible for the future-work channel.
                # Older API fallbacks exposed paper conclusions here; those are
                # results, not future work.
                if output_kind == "future_work" and not (
                    first_text(item.get("why_now"))
                    and first_text(item.get("first_step"))
                ):
                    continue
                identity = (
                    domain_id,
                    output_kind,
                    re.sub(r"\W+", " ", claim.lower()).strip(),
                    tuple(sorted(paper_key_from(paper) for paper in mapped)),
                )
                if identity in seen_narratives:
                    continue
                seen_narratives.add(identity)
                ledger.append(
                    {
                        "id": f"domain-{domain_id}-{output_kind}-{index + 1}",
                        "kind": output_kind,
                        "domain_id": domain_id,
                        "domain_title": detail.get("title"),
                        "candidate_claim": claim,
                        "confidence": item.get("confidence"),
                        "claim_type": item.get("claim_type"),
                        "period_start": item.get("period_start"),
                        "period_end": item.get("period_end"),
                        "why_now": item.get("why_now"),
                        "first_step": item.get("first_step"),
                        "support_paper_keys": [
                            paper_key_from(paper) for paper in mapped
                        ],
                        "support_paper_titles": [
                            paper.get("title") for paper in mapped
                        ],
                        "unresolved_support_paper_ids": unresolved,
                        "verification_status": "candidate_pending_primary_and_counterevidence_check",
                        "allowed_outline_use": "provisional_scaffold_only",
                    }
                )
        support_papers.extend(
            {
                **paper,
                "support_domain_id": domain_id,
                "support_kind": "domain_top_paper",
            }
            for paper in display.get("top_papers", []) or []
            if isinstance(paper, dict) and paper_key_from(paper)
        )
    scaffold = {
        "role": "candidate_scaffold_only",
        "warning": "Domain narratives are synthesized candidates. Verify material claims against primary papers and counter-evidence before scoring or drafting them as facts.",
        "domains": domains,
        "narrative_items": ledger,
    }
    return scaffold, support_papers


def _paper_pool_index(papers: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Index every frozen paper, preferring its ReaScholar key when available."""
    return {
        frozen_paper_key(paper): paper
        for paper in papers
        if frozen_paper_key(paper) and paper.get("title")
    }


def _compact_support_papers(
    item: dict[str, Any], pool_by_key: dict[str, dict[str, Any]]
) -> list[dict[str, Any]]:
    titles = item.get("support_paper_titles") or []
    title_by_key = {
        str(key): str(titles[index] or "")
        for index, key in enumerate(item.get("support_paper_keys") or [])
        if index < len(titles)
    }
    support: list[dict[str, Any]] = []
    for key in item.get("support_paper_keys") or []:
        paper = pool_by_key.get(str(key))
        if not paper:
            continue
        support.append(
            {
                "paper_key": str(key),
                "title": str(paper.get("title") or title_by_key.get(str(key)) or ""),
                "year": paper.get("year"),
                "in_frozen_paper_pool": True,
            }
        )
    return support


def _citation_relations(
    paper_details: Iterable[dict[str, Any]],
    pool_by_key: dict[str, dict[str, Any]],
    expansion_records: Iterable[dict[str, Any]] = (),
) -> list[dict[str, Any]]:
    """Return citation edges whose two endpoints are both in the frozen pool."""
    relations: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()

    def add(citing_key: str, cited_key: str) -> None:
        edge = (citing_key, cited_key)
        if (
            citing_key not in pool_by_key
            or cited_key not in pool_by_key
            or citing_key == cited_key
            or edge in seen
        ):
            return
        seen.add(edge)
        relations.append(
            {
                "relation": "cites",
                "citing_paper_key": citing_key,
                "citing_title": pool_by_key[citing_key].get("title"),
                "cited_paper_key": cited_key,
                "cited_title": pool_by_key[cited_key].get("title"),
                "status": "within_frozen_paper_pool",
            }
        )

    for detail in paper_details:
        source_key = paper_key_from(detail)
        display = detail.get("display") if isinstance(detail.get("display"), dict) else {}
        overview = display.get("overview") if isinstance(display.get("overview"), dict) else {}
        citations = overview.get("citations") if isinstance(overview.get("citations"), dict) else {}
        for reference in citations.get("references") or []:
            if isinstance(reference, dict):
                add(source_key, paper_key_from(reference))
        for citing in citations.get("cited_by") or []:
            if isinstance(citing, dict):
                add(paper_key_from(citing), source_key)

    s2_key_by_id = {
        str(paper.get("paperId") or ""): key
        for key, paper in pool_by_key.items()
        if paper.get("paperId")
    }
    for record in expansion_records:
        seed_key = str(record.get("seed_paper_key") or "")
        expanded_key = s2_key_by_id.get(
            str(record.get("expanded_paper_id") or ""), ""
        )
        if record.get("direction") == "reference":
            add(seed_key, expanded_key)
        elif record.get("direction") == "cited_by":
            add(expanded_key, seed_key)
    return relations


def build_structure_pack(
    scaffold: dict[str, Any],
    ledger: list[dict[str, Any]],
    papers: list[dict[str, Any]],
    paper_details: Iterable[dict[str, Any]],
    citation_expansion_records: Iterable[dict[str, Any]] = (),
) -> dict[str, Any]:
    """Build the compact, optional structure-only treatment for a frozen library."""
    pool_by_key = _paper_pool_index(papers)
    domains: list[dict[str, Any]] = []
    for domain in scaffold.get("domains") or []:
        overview = domain.get("overview") if isinstance(domain.get("overview"), dict) else {}
        domains.append(
            {
                "domain_id": domain.get("domain_id"),
                "title": domain.get("title"),
                "parent_domain": domain.get("l1_name_en"),
                "description": first_text(
                    overview.get("description"), overview.get("core_topic")
                ),
                "paper_count": domain.get("paper_count"),
                "status": "provisional_taxonomy",
            }
        )

    grouped: dict[str, list[dict[str, Any]]] = {
        "timeline": [],
        "gaps": [],
        "future_work": [],
    }
    kind_to_group = {
        "timeline": "timeline",
        "limitation": "gaps",
        "future_work": "future_work",
    }
    warnings: list[dict[str, Any]] = []
    for item in ledger:
        group = kind_to_group.get(str(item.get("kind") or ""))
        if not group:
            continue
        resolved_support = _compact_support_papers(item, pool_by_key)
        unresolved_ids = [
            str(value) for value in item.get("unresolved_support_paper_ids") or []
        ]
        missing_pool_keys = [
            str(key)
            for key in item.get("support_paper_keys") or []
            if str(key) not in pool_by_key
        ]
        grouped[group].append(
            {
                "id": item.get("id"),
                "domain_id": item.get("domain_id"),
                "domain_title": item.get("domain_title"),
                "candidate_claim": item.get("candidate_claim"),
                "period_start": item.get("period_start"),
                "period_end": item.get("period_end"),
                "why_now": item.get("why_now"),
                "first_step": item.get("first_step"),
                "confidence": item.get("confidence"),
                "claim_type": item.get("claim_type"),
                "support_papers": resolved_support,
                "verification_status": item.get("verification_status"),
                "allowed_use": "provisional_structure; verify claim against listed papers",
            }
        )
        if unresolved_ids or missing_pool_keys:
            warnings.append(
                {
                    "item_id": item.get("id"),
                    "unresolved_support_paper_ids": unresolved_ids,
                    "support_keys_absent_from_frozen_pool": missing_pool_keys,
                    "instruction": "Do not use these identifiers as citation evidence.",
                }
            )

    return {
        "schema_version": "reascholar-structure-pack-v1",
        "role": "provisional_structure",
        "paper_pool_size": len(papers),
        "paper_pool_reascholar_key_count": len(pool_by_key),
        "domains": domains,
        **grouped,
        "citation_relations": _citation_relations(
            paper_details, pool_by_key, citation_expansion_records
        ),
        "warnings": warnings,
    }


def render_structure_pack(pack: dict[str, Any]) -> str:
    lines = [
        "# ReaScholar structure pack (provisional)",
        "",
        "> The paper library is frozen. Use this pack only to organize synthesis; cite exact papers from the library and preserve uncertainty.",
        "",
    ]
    if pack.get("domains"):
        lines.extend(["## Candidate taxonomy", ""])
        for domain in pack["domains"]:
            description = f" — {domain['description']}" if domain.get("description") else ""
            lines.append(f"- {domain.get('title')} (Domain {domain.get('domain_id')}){description}")
        lines.append("")
    for key, heading in (
        ("timeline", "Supported evolution candidates"),
        ("gaps", "Limitation and gap candidates"),
        ("future_work", "Future-work candidates"),
    ):
        items = pack.get(key) or []
        if not items:
            continue
        lines.extend([f"## {heading}", ""])
        for item in items:
            support = "; ".join(
                str(paper.get("title") or "") for paper in item.get("support_papers") or []
            ) or "no support paper resolved in the frozen pool"
            period = ""
            if item.get("period_start") or item.get("period_end"):
                period = f" [{item.get('period_start') or '?'}-{item.get('period_end') or '?'}]"
            lines.append(
                f"- [PROVISIONAL]{period} {item.get('candidate_claim')} (listed support: {support})"
            )
        lines.append("")
    if pack.get("citation_relations"):
        lines.extend(["## Within-library citation relations", ""])
        for edge in pack["citation_relations"][:80]:
            lines.append(f"- {edge.get('citing_title')} -> {edge.get('cited_title')}")
        lines.append("")
    if pack.get("warnings"):
        lines.extend(
            [
                "## Evidence warnings",
                "",
                f"- {len(pack['warnings'])} structure items contain unresolved or out-of-pool support identifiers. They are not citation evidence.",
                "",
            ]
        )
    return "\n".join(lines)


def compact_search_topic(topic: str, max_terms: int = 8) -> str:
    """Keep domain-bearing terms in a form S2 keyword search can recall."""
    terms = [
        term
        for term in re.findall(r"[a-z0-9]+", topic.casefold())
        if term not in GENERIC_TOPIC_WORDS
    ]
    compact = " ".join(terms[:max_terms]).strip()
    return compact or topic.strip()


def stage_queries(topic: str, task_path: Path | None = None) -> list[str]:
    compact_topic = compact_search_topic(topic)
    if task_path is None or not task_path.exists():
        return [template.format(topic=compact_topic) for template in QUERY_TEMPLATES]
    try:
        import yaml
    except ImportError as exc:  # pragma: no cover - deployment dependency guard
        raise RuntimeError(f"PyYAML is required to read {task_path}") from exc
    payload = yaml.safe_load(task_path.read_text(encoding="utf-8")) or {}
    core = compact_search_topic(topic, max_terms=5)
    core_prefix = " ".join(core.split()[:2])
    queries = [core]
    for aspect in (payload.get("expected_aspects") or [])[:3]:
        if not isinstance(aspect, dict):
            continue
        axis = " ".join(
            [
                str(aspect.get("name") or ""),
                *(str(value) for value in aspect.get("keywords") or []),
            ]
        )
        query = compact_search_topic(f"{core_prefix} {axis}", max_terms=8)
        if query and query not in queries:
            queries.append(query)
    for template in QUERY_TEMPLATES[1:]:
        if len(queries) >= 4:
            break
        query = template.format(topic=core)
        if query not in queries:
            queries.append(query)
    return queries[:4]


def normalized_title(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.casefold()).strip()


def load_required_references(task_path: Path | None) -> list[dict[str, Any]]:
    if task_path is None or not task_path.exists():
        return []
    try:
        import yaml
    except ImportError as exc:  # pragma: no cover - deployment dependency guard
        raise RuntimeError(f"PyYAML is required to read {task_path}") from exc
    payload = yaml.safe_load(task_path.read_text(encoding="utf-8")) or {}
    references = payload.get("key_references") if isinstance(payload, dict) else []
    return [item for item in (references or []) if isinstance(item, dict)]


def load_task_cutoff_year(task_path: Path | None) -> int | None:
    cutoff = load_task_cutoff_date(task_path)
    return cutoff.year if cutoff else None


def load_task_cutoff_date(task_path: Path | None) -> date | None:
    if task_path is None or not task_path.exists():
        return None
    try:
        import yaml
    except ImportError as exc:  # pragma: no cover - deployment dependency guard
        raise RuntimeError(f"PyYAML is required to read {task_path}") from exc
    payload = yaml.safe_load(task_path.read_text(encoding="utf-8")) or {}
    raw = str(payload.get("cutoff_date") or "")
    try:
        return date.fromisoformat(raw)
    except ValueError:
        return None


def load_task_relevance_terms(task_path: Path | None, topic: str) -> set[str]:
    snippets = [topic]
    if task_path is not None and task_path.exists():
        try:
            import yaml
        except ImportError as exc:  # pragma: no cover - deployment dependency guard
            raise RuntimeError(f"PyYAML is required to read {task_path}") from exc
        payload = yaml.safe_load(task_path.read_text(encoding="utf-8")) or {}
        for aspect in payload.get("expected_aspects") or []:
            if not isinstance(aspect, dict):
                continue
            snippets.append(str(aspect.get("name") or ""))
            snippets.extend(str(value) for value in aspect.get("keywords") or [])
    return match_token_set(" ".join(snippets))


def citation_candidate_relevant(
    title: str,
    relevance_terms: set[str],
    primary_domain_terms: set[str],
) -> bool:
    candidate_terms = match_token_set(title)
    overlap = candidate_terms & relevance_terms
    return bool(overlap & primary_domain_terms) or len(overlap) >= 2


def search_candidate_relevant(
    title: str,
    primary_domain_terms: set[str],
    topic_signature_terms: set[str],
) -> bool:
    candidate_terms = match_token_set(title)
    return bool(candidate_terms & primary_domain_terms) or len(
        candidate_terms & topic_signature_terms
    ) >= 2


def paper_within_year_bounds(
    paper: dict[str, Any], year_from: int | None, year_to: int | None
) -> bool:
    try:
        year = int(paper.get("year") or 0)
    except (TypeError, ValueError):
        return True
    if not year:
        return True
    if year_from is not None and year < year_from:
        return False
    if year_to is not None and year > year_to:
        return False
    return True


def paper_within_date_cutoff(
    paper: dict[str, Any], cutoff: date | None
) -> bool:
    if cutoff is None:
        return True
    publication_date = str(paper.get("publicationDate") or "").strip()
    if publication_date:
        try:
            return date.fromisoformat(publication_date[:10]) <= cutoff
        except ValueError:
            pass
    external = (
        paper.get("externalIds")
        if isinstance(paper.get("externalIds"), dict)
        else {}
    )
    arxiv_id = str(external.get("ArXiv") or "")
    arxiv_match = re.match(r"^(\d{2})(\d{2})\.", arxiv_id)
    if arxiv_match:
        arxiv_year = 2000 + int(arxiv_match.group(1))
        arxiv_month = int(arxiv_match.group(2))
        if arxiv_year != cutoff.year:
            return arxiv_year < cutoff.year
        return arxiv_month <= cutoff.month
    try:
        year = int(paper.get("year") or 0)
    except (TypeError, ValueError):
        year = 0
    if not year:
        # A record without any date provenance cannot be proven to precede a
        # frozen cutoff and must not enter a causal benchmark snapshot.
        return False
    if year != cutoff.year:
        return year < cutoff.year
    # A same-year item without month/day provenance cannot be proven to meet
    # a mid-year cutoff.
    return cutoff.month == 12 and cutoff.day == 31


def select_topic_support_papers(
    papers: list[dict[str, Any]],
    selected_domains: list[dict[str, Any]],
    topic: str,
) -> list[dict[str, Any]]:
    """Keep only support papers whose titles remain task-specific."""

    if not selected_domains:
        return []
    primary_terms = match_token_set(str(selected_domains[0].get("title") or ""))
    selected_domain_ids = {int(domain["domain_id"]) for domain in selected_domains}
    secondary_domain_terms = set().union(
        *(
            match_token_set(str(domain.get("title") or ""))
            for domain in selected_domains[1:]
        )
    )
    topic_signature_terms = (
        match_token_set(topic)
        - match_token_set(" ".join(GENERIC_CITATION_WORDS))
        - secondary_domain_terms
    )
    selected: list[dict[str, Any]] = []
    for paper in papers:
        try:
            support_domain_id = int(paper.get("support_domain_id"))
        except (TypeError, ValueError):
            continue
        if support_domain_id not in selected_domain_ids:
            continue
        if search_candidate_relevant(
            str(paper.get("title") or ""),
            primary_terms,
            topic_signature_terms,
        ):
            selected.append(paper)
            continue
        try:
            year = int(paper.get("year") or 0)
        except (TypeError, ValueError):
            year = 0
        if (
            support_domain_id == int(selected_domains[0]["domain_id"])
            and paper.get("support_kind") == "domain_narrative_support"
            and year > 0
            and match_token_set(str(paper.get("title") or ""))
            & topic_signature_terms
        ):
            selected.append(paper)
    return selected


def prioritize_detail_candidates(
    search_papers: list[dict[str, Any]],
    support_papers: list[dict[str, Any]],
    selected_domains: list[dict[str, Any]],
) -> list[str]:
    """Spend structured-detail budget on search hits, then primary support."""

    primary_domain_id = (
        int(selected_domains[0]["domain_id"]) if selected_domains else None
    )
    primary_support = [
        paper
        for paper in support_papers
        if paper.get("support_domain_id") == primary_domain_id
    ]
    secondary_support = [
        paper
        for paper in support_papers
        if paper.get("support_domain_id") != primary_domain_id
    ]
    return list(
        dict.fromkeys(
            paper_key_from(paper)
            for paper in [*search_papers, *primary_support, *secondary_support]
            if paper_key_from(paper)
        )
    )


def search_reascholar(
    query: str, mode: str, domain_ids: list[int], args: argparse.Namespace
) -> dict[str, Any]:
    filters: dict[str, Any] = {"l2_domain_ids": domain_ids}
    if args.year_from:
        filters["year_from"] = args.year_from
    if args.year_to:
        filters["year_to"] = args.year_to
    return request_json(
        REASCHOLAR_BASE,
        "/api/search",
        payload={
            "query": query,
            "top_k": args.per_query,
            "mode": mode,
            "response_format": "structured",
            "filters": filters,
            "include_details": False,
            "include_raw": False,
        },
    )


def search_s2(
    query: str, args: argparse.Namespace, limit: int | None = None
) -> dict[str, Any]:
    year = ""
    if args.year_from or args.year_to:
        year = f"{args.year_from or ''}-{args.year_to or ''}"
    params = {
        "query": query,
        "limit": limit or args.per_query,
        "year": year,
        "fields": S2_FIELDS,
    }
    return cached_s2_get("/paper/search", params)


def cached_s2_get(path: str, params: dict[str, Any]) -> dict[str, Any]:
    """Fetch one S2 GET response through the credential-free shared cache."""

    cache_root = os.getenv("REASFLOW_SHARED_S2_CACHE_DIR", "").strip()
    if not cache_root:
        return request_json(S2_BASE, path, params=params, s2=True)

    # The cache key contains endpoint parameters but never the credential.
    cache_key = hashlib.sha256(
        json.dumps(
            {"path": path, "params": params},
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
    cache_dir = Path(cache_root).expanduser().resolve()
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_path = cache_dir / f"{cache_key}.json"
    lock_path = cache_dir / f"{cache_key}.lock"
    with lock_path.open("a+", encoding="utf-8") as lock_handle:
        fcntl.flock(lock_handle.fileno(), fcntl.LOCK_EX)
        if cache_path.is_file():
            return json.loads(cache_path.read_text(encoding="utf-8"))
        response = request_json(S2_BASE, path, params=params, s2=True)
        temporary = cache_path.with_suffix(".tmp")
        write_json(temporary, response)
        temporary.replace(cache_path)
        return response


def audit_required_s2_anchors(
    required_references: list[dict[str, Any]],
    args: argparse.Namespace,
    out: Path,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], int]:
    """Run the same exact-title S2 anchor audit in both retrieval profiles."""
    papers: list[dict[str, Any]] = []
    audit: list[dict[str, Any]] = []
    query_count = 0
    for anchor_index, anchor in enumerate(required_references, start=1):
        canonical = str(anchor.get("title") or "").strip()
        aliases = [str(item).strip() for item in anchor.get("aliases") or [] if str(item).strip()]
        accepted = {normalized_title(canonical), *(normalized_title(item) for item in aliases)}
        accepted.discard("")
        found: dict[str, Any] | None = None
        attempts: list[dict[str, Any]] = []
        for attempt_index, query in enumerate([canonical, *aliases[:2]], start=1):
            if not query:
                continue
            query_count += 1
            try:
                response = search_s2(query, args, limit=10)
                write_json(
                    out
                    / "searches"
                    / f"anchor_{anchor_index:02d}_{attempt_index:02d}_semantic_scholar.json",
                    response,
                )
                items = [item for item in response.get("data", []) if isinstance(item, dict)]
                found = next(
                    (
                        item
                        for item in items
                        if normalized_title(str(item.get("title") or "")) in accepted
                    ),
                    None,
                )
                attempts.append(
                    {
                        "query": query,
                        "status": "ok",
                        "returned": len(items),
                        "exact_match": bool(found),
                    }
                )
            except Exception as exc:
                attempts.append(
                    {
                        "query": query,
                        "status": "failed",
                        "returned": 0,
                        "exact_match": False,
                        "error": str(exc),
                    }
                )
            if found is not None:
                papers.append(normalize_s2(found, f"semantic_scholar:required_anchor_{anchor_index}"))
                break
        audit.append(
            {
                "canonical_title": canonical,
                "status": "resolved_exact_title" if found is not None else "missing_after_bounded_audit",
                "resolved_title": str(found.get("title") or "") if found else None,
                "attempts": attempts,
            }
        )
    return papers, audit, query_count


def batch_details(keys: list[str]) -> dict[str, dict[str, Any]]:
    details: dict[str, dict[str, Any]] = {}
    for start in range(0, len(keys), 50):
        chunk = keys[start : start + 50]
        response = request_json(
            REASCHOLAR_BASE,
            "/api/search/papers/batch",
            payload={
                "paper_keys": chunk,
                "include_markdown": False,
                "include_raw": False,
                "include_prover": False,
                "statement_limit": 8,
            },
        )
        for item in response.get("papers", []):
            if isinstance(item, dict) and paper_key_from(item):
                details[paper_key_from(item)] = item
    return details


def expand_citation_neighbors(
    paper_details: Iterable[dict[str, Any]],
    existing_papers: Iterable[dict[str, Any]],
    *,
    max_seeds: int = 12,
    backward_per_seed: int = 3,
    forward_per_seed: int = 2,
    max_new_papers: int = 30,
    relevance_terms: set[str] | None = None,
    primary_domain_terms: set[str] | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Select a bounded one-hop ReaScholar citation expansion with provenance."""
    known_tokens = set().union(*(identity_tokens(paper) for paper in existing_papers))
    selected: list[dict[str, Any]] = []
    provenance: list[dict[str, Any]] = []
    used_seed_count = 0
    for detail in paper_details:
        seed_key = paper_key_from(detail)
        display = detail.get("display") if isinstance(detail.get("display"), dict) else {}
        overview = display.get("overview") if isinstance(display.get("overview"), dict) else {}
        citations = overview.get("citations") if isinstance(overview.get("citations"), dict) else {}
        directions = (
            ("reference", citations.get("references") or [], backward_per_seed),
            ("cited_by", citations.get("cited_by") or [], forward_per_seed),
        )
        if not seed_key or not any(relations for _, relations, _ in directions):
            continue
        if used_seed_count >= max_seeds:
            break
        used_seed_count += 1
        for direction, relations, per_seed_limit in directions:
            retained_for_seed = 0
            for relation in relations:
                if retained_for_seed >= per_seed_limit or len(selected) >= max_new_papers:
                    break
                if not isinstance(relation, dict):
                    continue
                candidate = normalize_reascholar(
                    relation,
                    None,
                    f"reascholar:citation_{direction}:{seed_key}",
                )
                if relevance_terms is not None and not citation_candidate_relevant(
                    str(candidate.get("title") or ""),
                    relevance_terms,
                    primary_domain_terms or set(),
                ):
                    continue
                tokens = identity_tokens(candidate)
                if not candidate.get("title") or not tokens or not tokens.isdisjoint(known_tokens):
                    continue
                candidate["citation_expansion"] = {
                    "seed_paper_key": seed_key,
                    "direction": direction,
                    "hop": 1,
                }
                selected.append(candidate)
                known_tokens.update(tokens)
                retained_for_seed += 1
                provenance.append(
                    {
                        "provider": "reascholar",
                        "seed_paper_key": seed_key,
                        "expanded_paper_key": paper_key_from(candidate),
                        "expanded_title": candidate.get("title"),
                        "direction": direction,
                        "hop": 1,
                    }
                )
            if len(selected) >= max_new_papers:
                break
        if len(selected) >= max_new_papers:
            break
    return selected, provenance


def semantic_scholar_identifier(paper: dict[str, Any]) -> str:
    external = (
        paper.get("externalIds")
        if isinstance(paper.get("externalIds"), dict)
        else {}
    )
    doi = first_text(external.get("DOI"), paper.get("doi")).casefold()
    doi = re.sub(r"^https?://(?:dx\.)?doi\.org/", "", doi).strip()
    if doi.startswith("10."):
        return f"DOI:{doi}"
    arxiv = first_text(external.get("ArXiv"), external.get("arXiv"))
    arxiv = re.sub(r"v\d+$", "", arxiv, flags=re.IGNORECASE).strip()
    if arxiv:
        return f"ARXIV:{arxiv}"
    paper_id = str(paper.get("paperId") or "").strip()
    return paper_id if paper_id and not paper_id.startswith("reascholar:") else ""


def expand_s2_citation_neighbors(
    seed_papers: Iterable[dict[str, Any]],
    existing_papers: Iterable[dict[str, Any]],
    *,
    max_seeds: int,
    backward_per_seed: int,
    forward_per_seed: int,
    max_new_papers: int,
    relevance_terms: set[str],
    primary_domain_terms: set[str],
    year_from: int | None,
    year_to: int | None,
    cutoff_date: date | None,
    fetch: Callable[[str, dict[str, Any]], dict[str, Any]] = cached_s2_get,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    """Fill a sparse local graph with bounded, cached S2 one-hop neighbors."""

    known_tokens = set().union(*(identity_tokens(paper) for paper in existing_papers))
    selected: list[dict[str, Any]] = []
    provenance: list[dict[str, Any]] = []
    requests: list[dict[str, Any]] = []
    used_identifiers: set[str] = set()
    for seed in seed_papers:
        if len(used_identifiers) >= max_seeds or len(selected) >= max_new_papers:
            break
        identifier = semantic_scholar_identifier(seed)
        if not identifier or identifier in used_identifiers:
            continue
        used_identifiers.add(identifier)
        seed_key = paper_key_from(seed) or identifier
        directions = (
            ("reference", "references", "citedPaper", backward_per_seed),
            ("cited_by", "citations", "citingPaper", forward_per_seed),
        )
        encoded_identifier = urllib.parse.quote(identifier, safe=":")
        for direction, endpoint, record_field, per_seed_limit in directions:
            if per_seed_limit <= 0 or len(selected) >= max_new_papers:
                continue
            path = f"/paper/{encoded_identifier}/{endpoint}"
            params = {"limit": 50, "fields": S2_FIELDS}
            request_record = {
                "provider": "semantic_scholar",
                "seed_paper_key": seed_key,
                "seed_identifier": identifier,
                "direction": direction,
                "path": path,
                "status": "ok",
                "returned": 0,
                "retained": 0,
            }
            try:
                response = fetch(path, params)
            except Exception as exc:
                request_record.update({"status": "failed", "error": str(exc)})
                requests.append(request_record)
                continue
            rows = [
                item
                for item in (response.get("data") or [])
                if isinstance(item, dict)
            ]
            request_record["returned"] = len(rows)
            retained = 0
            for row in rows:
                raw_candidate = row.get(record_field)
                if not isinstance(raw_candidate, dict):
                    continue
                candidate = normalize_s2(
                    raw_candidate,
                    f"semantic_scholar:citation_{direction}:{seed_key}",
                )
                if not citation_candidate_relevant(
                    str(candidate.get("title") or ""),
                    relevance_terms,
                    primary_domain_terms,
                ):
                    continue
                if not paper_within_year_bounds(candidate, year_from, year_to):
                    continue
                if not paper_within_date_cutoff(candidate, cutoff_date):
                    continue
                tokens = identity_tokens(candidate)
                if (
                    not candidate.get("title")
                    or not tokens
                    or not tokens.isdisjoint(known_tokens)
                ):
                    continue
                candidate["citation_expansion"] = {
                    "provider": "semantic_scholar",
                    "seed_paper_key": seed_key,
                    "direction": direction,
                    "hop": 1,
                }
                selected.append(candidate)
                known_tokens.update(tokens)
                retained += 1
                provenance.append(
                    {
                        "provider": "semantic_scholar",
                        "seed_paper_key": seed_key,
                        "expanded_paper_id": candidate.get("paperId"),
                        "expanded_title": candidate.get("title"),
                        "direction": direction,
                        "hop": 1,
                    }
                )
                if retained >= per_seed_limit or len(selected) >= max_new_papers:
                    break
            request_record["retained"] = retained
            requests.append(request_record)
    return selected, provenance, requests


def render_outline_context(
    scaffold: dict[str, Any], ledger: list[dict[str, Any]]
) -> str:
    lines = [
        "# ReaScholar domain scaffold (provisional)",
        "",
        "> Do not copy this narrative as fact. Use it to organize questions and verify each material claim against papers and counter-evidence.",
        "",
    ]
    if not scaffold.get("domains"):
        lines.extend(["Domain context is unavailable in this retrieval profile.", ""])
        return "\n".join(lines)
    for domain in scaffold["domains"]:
        lines.extend([f"## {domain['title']} (L2 {domain['domain_id']})", ""])
        overview = domain.get("overview") or {}
        description = first_text(
            overview.get("description"), overview.get("core_topic")
        )
        if description:
            lines.extend([description, ""])
        for kind, heading in (
            ("timeline", "Timeline candidates"),
            ("limitation", "Limitation candidates"),
            ("future_work", "Future-work candidates"),
        ):
            items = [
                item
                for item in ledger
                if item["domain_id"] == domain["domain_id"] and item["kind"] == kind
            ]
            if not items:
                continue
            lines.extend([f"### {heading}", ""])
            for item in items:
                support = (
                    "; ".join(item["support_paper_titles"])
                    or "no resolved support paper"
                )
                lines.append(
                    f"- [PROVISIONAL] {item['candidate_claim']} (candidate support: {support})"
                )
            lines.append("")
    return "\n".join(lines)


def run(args: argparse.Namespace) -> int:
    if args.profile not in PROFILES:
        raise RuntimeError(f"Unknown profile: {args.profile}")
    out = args.out_dir.resolve()
    out.mkdir(parents=True, exist_ok=True)
    started = utc_now()
    task_path_raw = str(getattr(args, "task_path", "") or "")
    task_path = Path(task_path_raw).expanduser().resolve() if task_path_raw else None
    queries = stage_queries(args.topic, task_path)
    required_references = load_required_references(task_path)
    task_cutoff_date = load_task_cutoff_date(task_path)
    task_cutoff_year = task_cutoff_date.year if task_cutoff_date else None
    if args.year_to is None and task_cutoff_year is not None:
        args.year_to = task_cutoff_year
    search_records: list[dict[str, Any]] = []
    all_papers: list[dict[str, Any]] = []
    selected: list[dict[str, Any]] = []
    detail_map: dict[str, dict[str, Any]] = {}
    errors: list[dict[str, str]] = []
    citation_expansion_records: list[dict[str, Any]] = []
    citation_expansion_requests: list[dict[str, Any]] = []
    local_citation_expansion_count = 0
    s2_citation_expansion_count = 0

    if args.profile == "reascholar-s2":
        discovery = discover_domains(args.topic, args)
        selected = select_domains(discovery, args.topic, args)
        discovery["client_selected_domain_ids"] = [
            item["domain_id"] for item in selected
        ]
        discovery["selection_policy"] = (
            "manual"
            if args.domain_id
            else "client lexical+topic relevance ranking; inspect before high-stakes use"
        )
        write_json(out / "domain_discovery.json", discovery)
        if args.discover_only:
            print(f"Wrote domain discovery to {out / 'domain_discovery.json'}")
            return 0
        details = fetch_domain_details(selected)
        for item in details:
            write_json(out / "domains" / f"domain_{item['domain_id']}.json", item)
        scaffold, mapped_support = build_domain_scaffold(details)
        ledger = scaffold["narrative_items"]
        domain_ids = [int(item["domain_id"]) for item in selected]
        generic_citation_terms = match_token_set(" ".join(GENERIC_CITATION_WORDS))
        secondary_domain_terms = set().union(
            *(
                match_token_set(str(domain.get("title") or ""))
                for domain in selected[1:]
            )
        )
        citation_relevance_terms = (
            load_task_relevance_terms(task_path, args.topic)
            - generic_citation_terms
            - secondary_domain_terms
        )
        primary_domain_terms = (
            match_token_set(str(selected[0].get("title") or ""))
            if selected
            else set()
        )
        topic_signature_terms = (
            match_token_set(args.topic)
            - generic_citation_terms
            - secondary_domain_terms
        )
        modes = ("agent", "fast", "algorithm")
        for index, (query, mode) in enumerate(zip(queries[:3], modes), start=1):
            try:
                response = search_reascholar(query, mode, domain_ids, args)
                write_json(
                    out / "searches" / f"q{index}_reascholar_{mode}.json", response
                )
                raw_count = int(
                    response.get("result_count") or len(response.get("results", []))
                )
                retained_count = 0
                for item in response.get("results", []):
                    if isinstance(item, dict) and item.get("result_type") == "paper":
                        if not search_candidate_relevant(
                            str(item.get("title") or ""),
                            primary_domain_terms,
                            topic_signature_terms,
                        ):
                            continue
                        all_papers.append(
                            normalize_reascholar(
                                item, None, f"reascholar:{mode}:q{index}"
                            )
                        )
                        retained_count += 1
                search_records.append(
                    {
                        "query": query,
                        "provider": "reascholar",
                        "mode": mode,
                        "count": retained_count,
                        "raw_count": raw_count,
                        "retained_count": retained_count,
                        "status": "ok",
                    }
                )
            except Exception as exc:
                errors.append(
                    {"route": f"reascholar:{mode}:q{index}", "error": str(exc)}
                )
                search_records.append(
                    {
                        "query": query,
                        "provider": "reascholar",
                        "mode": mode,
                        "count": 0,
                        "status": "failed",
                    }
                )
        for domain in selected:
            for anchor in domain.get("anchor_papers", []) or []:
                if isinstance(anchor, dict) and paper_key_from(anchor):
                    mapped_support.append({
                        **anchor,
                        "support_domain_id": int(domain["domain_id"]),
                        "support_kind": "domain_discovery_anchor",
                    })
        mapped_support = select_topic_support_papers(
            mapped_support, selected, args.topic
        )
        keys = prioritize_detail_candidates(all_papers, mapped_support, selected)
        keys = keys[: args.max_details]
        if keys:
            try:
                detail_map = batch_details(keys)
            except Exception as exc:
                errors.append({"route": "reascholar:paper_batch", "error": str(exc)})
        normalized_support: list[dict[str, Any]] = []
        for paper in mapped_support:
            key = paper_key_from(paper)
            normalized_support.append(
                normalize_reascholar(
                    paper, detail_map.get(key), "domain_support_or_anchor"
                )
            )
        enriched_search: list[dict[str, Any]] = []
        for paper in all_papers:
            key = paper_key_from(paper)
            if key and key in detail_map:
                routes = paper.get("retrieval_routes") or ["reascholar_search"]
                enriched_search.append(
                    normalize_reascholar(paper, detail_map[key], routes[0])
                )
            else:
                enriched_search.append(paper)
        all_papers = [*normalized_support, *enriched_search]
        ordered_details = [detail_map[key] for key in keys if key in detail_map]
        citation_neighbors, citation_expansion_records = expand_citation_neighbors(
            ordered_details,
            all_papers,
            max_seeds=int(getattr(args, "citation_seed_limit", 12)),
            backward_per_seed=int(getattr(args, "citation_backward_per_seed", 3)),
            forward_per_seed=int(getattr(args, "citation_forward_per_seed", 2)),
            max_new_papers=int(getattr(args, "citation_expansion_limit", 30)),
            relevance_terms=citation_relevance_terms,
            primary_domain_terms=primary_domain_terms,
        )
        local_citation_expansion_count = len(citation_neighbors)
        neighbor_keys = [paper_key_from(paper) for paper in citation_neighbors]
        neighbor_keys = [key for key in neighbor_keys if key]
        neighbor_details: dict[str, dict[str, Any]] = {}
        if neighbor_keys:
            try:
                neighbor_details = batch_details(neighbor_keys)
                detail_map.update(neighbor_details)
            except Exception as exc:
                errors.append({"route": "reascholar:citation_expansion_batch", "error": str(exc)})
        all_papers.extend(
            normalize_reascholar(
                paper,
                neighbor_details.get(paper_key_from(paper)),
                (paper.get("retrieval_routes") or ["reascholar:citation_expansion"])[0],
            )
            for paper in citation_neighbors
        )
        minimum_expansion = int(getattr(args, "citation_expansion_min", 12))
        expansion_limit = int(getattr(args, "citation_expansion_limit", 30))
        if len(citation_expansion_records) < minimum_expansion:
            seed_by_key = {
                paper_key_from(paper): paper
                for paper in all_papers
                if paper_key_from(paper)
            }
            seed_papers = [seed_by_key[key] for key in keys if key in seed_by_key]
            s2_neighbors, s2_records, citation_expansion_requests = (
                expand_s2_citation_neighbors(
                    seed_papers,
                    all_papers,
                    max_seeds=int(getattr(args, "citation_seed_limit", 12)),
                    backward_per_seed=int(
                        getattr(args, "citation_backward_per_seed", 3)
                    ),
                    forward_per_seed=int(
                        getattr(args, "citation_forward_per_seed", 2)
                    ),
                    max_new_papers=max(
                        0, expansion_limit - len(citation_expansion_records)
                    ),
                    relevance_terms=citation_relevance_terms,
                    primary_domain_terms=primary_domain_terms,
                    year_from=args.year_from,
                    year_to=args.year_to,
                    cutoff_date=task_cutoff_date,
                )
            )
            all_papers.extend(s2_neighbors)
            citation_expansion_records.extend(s2_records)
            s2_citation_expansion_count = len(s2_neighbors)
        for item in ledger:
            resolved = [key for key in item["support_paper_keys"] if key in detail_map]
            item["detail_retrieved_paper_keys"] = resolved
            item["verification_status"] = (
                "mapped_details_retrieved_still_requires_claim_check"
                if resolved
                else "candidate_pending_primary_and_counterevidence_check"
            )
        write_json(out / "domain_scaffold.json", scaffold)
        write_json(out / "evidence_ledger.json", {"items": ledger})
        (out / "outline_context.md").write_text(
            render_outline_context(scaffold, ledger), encoding="utf-8"
        )
    else:
        scaffold = {
            "role": "not_available_in_profile",
            "warning": "The s2-only baseline intentionally makes no ReaScholar Domain request.",
            "domains": [],
            "narrative_items": [],
        }
        write_json(out / "domain_scaffold.json", scaffold)
        write_json(out / "evidence_ledger.json", {"items": []})
        write_json(
            out / "domain_discovery.json",
            {"profile": "s2-only", "status": "not_requested"},
        )
        (out / "outline_context.md").write_text(
            render_outline_context(scaffold, []), encoding="utf-8"
        )
    write_json(
        out / "citation_expansion.json",
        {
            "profile": args.profile,
            "policy": {
                "hop_limit": 1,
                "seed_limit": int(getattr(args, "citation_seed_limit", 12)),
                "backward_per_seed": int(getattr(args, "citation_backward_per_seed", 3)),
                "forward_per_seed": int(getattr(args, "citation_forward_per_seed", 2)),
                "minimum_before_s2_fallback": int(
                    getattr(args, "citation_expansion_min", 12)
                ),
                "new_paper_limit": int(
                    getattr(args, "citation_expansion_limit", 30)
                ),
                "relevance_gate": "task expected-aspect overlap or topic signature term",
                "s2_fallback": "bounded cached one-hop expansion from ReaScholar-selected seeds",
            },
            "expanded_paper_count": len(citation_expansion_records),
            "local_reascholar_expanded_paper_count": local_citation_expansion_count,
            "s2_fallback_expanded_paper_count": s2_citation_expansion_count,
            "s2_fallback_requests": citation_expansion_requests,
            "records": citation_expansion_records,
        },
    )

    # The S2 evidence core is deliberately identical in both profiles. ReaScholar is
    # an additive treatment: it may contribute Domain candidates and structure, but
    # it must never replace a baseline S2 query or make a large Domain pool suppress
    # the ordinary evidence path.
    for index, query in enumerate(queries, start=1):
        route = f"semantic_scholar:q{index}"
        try:
            response = search_s2(query, args)
            write_json(
                out / "searches" / f"q{index}_semantic_scholar.json", response
            )
            items = [
                item for item in response.get("data", []) if isinstance(item, dict)
            ]
            search_records.append(
                {
                    "query": query,
                    "provider": "semantic_scholar",
                    "mode": "paper_search",
                    "stratum": "shared_s2_core",
                    "count": len(items),
                    "status": "ok",
                }
            )
            all_papers.extend(normalize_s2(item, route) for item in items)
        except Exception as exc:
            errors.append({"route": route, "error": str(exc)})
            search_records.append(
                {
                    "query": query,
                    "provider": "semantic_scholar",
                    "mode": "paper_search",
                    "stratum": "shared_s2_core",
                    "count": 0,
                    "status": "failed",
                }
            )

    anchor_papers, anchor_audit, anchor_query_count = audit_required_s2_anchors(
        required_references, args, out
    )
    all_papers.extend(anchor_papers)
    write_json(
        out / "required_anchor_audit.json",
        {
            "task_path": str(task_path) if task_path else None,
            "query_count": anchor_query_count,
            "resolved_count": len(anchor_papers),
            "required_count": len(required_references),
            "anchors": anchor_audit,
        },
    )

    unfiltered_record_count = len(all_papers)
    year_bounded_papers = [
        paper
        for paper in all_papers
        if paper_within_year_bounds(paper, args.year_from, args.year_to)
    ]
    year_filtered_record_count = unfiltered_record_count - len(year_bounded_papers)
    cutoff_rejected_papers = [
        paper
        for paper in year_bounded_papers
        if not paper_within_date_cutoff(paper, task_cutoff_date)
    ]
    all_papers = [
        paper
        for paper in year_bounded_papers
        if paper_within_date_cutoff(paper, task_cutoff_date)
    ]
    cutoff_date_filtered_record_count = len(year_bounded_papers) - len(all_papers)
    shared_s2_cutoff_filtered_record_count = sum(
        "semantic_scholar" in set(paper.get("sources") or [])
        for paper in cutoff_rejected_papers
    )
    reascholar_cutoff_filtered_record_count = sum(
        "reascholar" in set(paper.get("sources") or [])
        for paper in cutoff_rejected_papers
    )
    papers = merge_papers(all_papers)
    duplicate_tokens = duplicate_identity_tokens(papers)
    dedup_report = {
        "schema_version": "canonical-reference-dedup-v1",
        "input_record_count": len(all_papers),
        "canonical_paper_count": len(papers),
        "merged_record_count": len(all_papers) - len(papers),
        "duplicate_canonical_identity_count": len(duplicate_tokens),
        "duplicate_canonical_identities": duplicate_tokens,
        "gate_passed": not duplicate_tokens,
    }
    write_json(out / "dedup_report.json", dedup_report)
    if duplicate_tokens:
        raise RuntimeError(
            f"canonical reference deduplication failed: {len(duplicate_tokens)} duplicate identities remain"
        )
    with (out / "paper_pool.jsonl").open("w", encoding="utf-8") as handle:
        for paper in papers:
            handle.write(json.dumps(paper, ensure_ascii=False) + "\n")
    write_json(
        out / "paper_details.json",
        {"count": len(detail_map), "papers": list(detail_map.values())},
    )
    structure_pack = build_structure_pack(
        scaffold,
        scaffold.get("narrative_items") or [],
        papers,
        detail_map.values(),
        citation_expansion_records,
    )
    write_json(out / "structure_pack.json", structure_pack)
    (out / "structure_pack.md").write_text(
        render_structure_pack(structure_pack), encoding="utf-8"
    )
    s2_records = [
        item
        for item in search_records
        if item.get("stratum") == "shared_s2_core"
    ]
    nonempty_s2_queries = sum(
        item.get("status") == "ok" and int(item.get("count") or 0) > 0
        for item in s2_records
    )
    min_nonempty_s2_queries = int(getattr(args, "min_nonempty_s2_queries", 3))
    s2_core_ok = nonempty_s2_queries >= min_nonempty_s2_queries
    if not s2_core_ok:
        errors.append(
            {
                "route": "semantic_scholar:shared_s2_core_guard",
                "error": (
                    f"Only {nonempty_s2_queries}/{len(queries)} shared S2 queries "
                    f"returned papers; required at least {min_nonempty_s2_queries}."
                ),
            }
        )
    manifest = {
        "schema_version": "reasflow-two-stage-v1",
        "topic": args.topic,
        "topic_sha256": hashlib.sha256(args.topic.encode("utf-8")).hexdigest(),
        "profile": args.profile,
        "started_at": started,
        "completed_at": utc_now(),
        "reascholar_base_url": REASCHOLAR_BASE
        if args.profile == "reascholar-s2"
        else None,
        "semantic_scholar_key_configured": bool(api_key()),
        "shared_s2_snapshot_cache": {
            "enabled": bool(os.getenv("REASFLOW_SHARED_S2_CACHE_DIR", "").strip()),
            "key_policy": "sha256(endpoint path + sorted request parameters)",
            "credential_in_key": False,
        },
        # Kept for compatibility: this is the invariant baseline paper-search
        # budget. The additive ReaScholar budget is reported separately below.
        "stage_two_query_budget": len(queries),
        "shared_s2_query_budget": len(queries),
        "additive_reascholar_query_budget": 3
        if args.profile == "reascholar-s2"
        else 0,
        "total_paper_search_query_budget": len(queries)
        + (3 if args.profile == "reascholar-s2" else 0),
        "shared_s2_anchor_query_count": anchor_query_count,
        "required_anchor_count": len(required_references),
        "resolved_required_anchor_count": len(anchor_papers),
        "required_anchor_audit_path": str(out / "required_anchor_audit.json"),
        "per_query_limit": args.per_query,
        "query_family": queries,
        "query_topic_compaction": compact_search_topic(args.topic),
        "year_from": args.year_from,
        "year_to": args.year_to,
        "task_cutoff_year": task_cutoff_year,
        "task_cutoff_date": task_cutoff_date.isoformat()
        if task_cutoff_date
        else None,
        "year_filtered_record_count": year_filtered_record_count,
        "cutoff_date_filtered_record_count": cutoff_date_filtered_record_count,
        "shared_s2_cutoff_filtered_record_count": (
            shared_s2_cutoff_filtered_record_count
        ),
        "reascholar_cutoff_filtered_record_count": (
            reascholar_cutoff_filtered_record_count
        ),
        "selected_domains": [
            {
                "domain_id": item.get("domain_id"),
                "title": item.get("title"),
                "l1_domain_id": item.get("l1_domain_id"),
            }
            for item in selected
        ],
        "searches": search_records,
        "shared_s2_nonempty_query_count": nonempty_s2_queries,
        "shared_s2_returned_record_count": sum(
            int(item.get("count") or 0) for item in s2_records
        ),
        "shared_s2_min_nonempty_queries": min_nonempty_s2_queries,
        "shared_s2_core_ok": s2_core_ok,
        "unique_paper_count": len(papers),
        "citation_expanded_paper_count": len(citation_expansion_records),
        "local_citation_expanded_paper_count": local_citation_expansion_count,
        "s2_citation_expanded_paper_count": s2_citation_expansion_count,
        "additive_s2_citation_query_count": len(citation_expansion_requests),
        "duplicate_canonical_identity_count": len(duplicate_tokens),
        "canonical_reference_gate_passed": not duplicate_tokens,
        "structured_detail_count": len(detail_map),
        "structure_pack_counts": {
            key: len(structure_pack.get(key) or [])
            for key in (
                "domains",
                "timeline",
                "gaps",
                "future_work",
                "citation_relations",
                "warnings",
            )
        },
        "errors": errors,
        "domain_policy": "candidate_scaffold_only; primary-paper and counter-evidence verification required",
    }
    write_json(out / "retrieval_manifest.json", manifest)
    print(f"profile={args.profile} papers={len(papers)} errors={len(errors)} out={out}")
    return 0 if s2_core_ok else 2


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(description=__doc__)
    value.add_argument("--topic", required=True)
    value.add_argument("--profile", choices=sorted(PROFILES), default="reascholar-s2")
    value.add_argument("--out-dir", type=Path, required=True)
    value.add_argument("--discover-only", action="store_true")
    value.add_argument("--domain-id", type=int, action="append", default=[])
    value.add_argument("--discovery-count", type=int, default=8)
    value.add_argument("--domain-count", type=int, default=3)
    value.add_argument("--search-depth", type=int, default=160)
    value.add_argument("--anchor-papers", type=int, default=3)
    value.add_argument("--per-query", type=int, default=60)
    value.add_argument("--max-details", type=int, default=50)
    value.add_argument("--citation-seed-limit", type=int, default=12)
    value.add_argument("--citation-backward-per-seed", type=int, default=3)
    value.add_argument("--citation-forward-per-seed", type=int, default=2)
    value.add_argument("--citation-expansion-limit", type=int, default=30)
    value.add_argument("--citation-expansion-min", type=int, default=12)
    value.add_argument("--year-from", type=int, default=None)
    value.add_argument("--year-to", type=int, default=None)
    value.add_argument("--min-nonempty-s2-queries", type=int, default=3)
    value.add_argument("--task-path", default="")
    return value


def main() -> int:
    args = parser().parse_args()
    if args.discover_only and args.profile == "s2-only":
        print(
            "Error: --discover-only requires the reascholar-s2 profile", file=sys.stderr
        )
        return 2
    if not 1 <= args.domain_count <= 5:
        print("Error: --domain-count must be between 1 and 5", file=sys.stderr)
        return 2
    if not 1 <= args.per_query <= 100:
        print("Error: --per-query must be between 1 and 100", file=sys.stderr)
        return 2
    try:
        return run(args)
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
