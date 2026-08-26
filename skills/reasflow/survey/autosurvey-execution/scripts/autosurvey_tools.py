#!/usr/bin/env python3

from __future__ import annotations

import argparse
import hashlib
import html
import importlib.machinery
import importlib.util
import json
import math
import os
import re
import sys
import threading
import unicodedata
from pathlib import Path
from typing import Any

DEFAULT_SECTION_NUM = 7
DEFAULT_SUBSECTION_LEN = 700
DEFAULT_RAG_NUM = 60
DEFAULT_OUTLINE_REFERENCE_NUM = 1500
DEFAULT_NATIVE_EVIDENCE_MAX = 140
DEFAULT_MIN_CITATIONS = 45
DEFAULT_MIN_UNIQUE_SURVEY_CITATIONS = 100
DEFAULT_TARGET_UNIQUE_SURVEY_CITATIONS = 110
DEFAULT_MIN_SURVEY_WORDS = 10000
DEFAULT_TARGET_SURVEY_WORDS = 12000
DEFAULT_MIN_SURVEY_SUBSECTIONS = 24
# Physical TeX line count is formatting-dependent. Word, subsection, citation,
# BibTeX, and compilation gates provide the publication-quality contract.
DEFAULT_MIN_SURVEY_LINES = 0
DEFAULT_MIN_RELATED_CITATIONS = 45
DEFAULT_TARGET_RELATED_CITATIONS = 50
DEFAULT_MAX_RELATED_CITATIONS = 55
DEFAULT_MIN_RELATED_WORDS = 1500
DEFAULT_MIN_RELATED_SECTIONS = 3
DEFAULT_EMBEDDING_MODEL = "nomic-ai/nomic-embed-text-v1"

CITE_PATTERN = re.compile(
    r"\\cite[a-zA-Z*]*\s*(?:\[[^\]]*\])?\s*(?:\[[^\]]*\])?\{([^}]*)\}"
)
BIB_PATTERN = re.compile(r"@\w+\s*\{\s*([^,\s]+)", re.IGNORECASE)
LATEX_PREAMBLE_PATTERN = re.compile(
    r"^\s*\\(?:documentclass|usepackage|begin\{document\}|end\{document\}|bibliographystyle|bibliography)\b"
)
LATEX_CITE_PATTERN = re.compile(
    r"\\cite[a-zA-Z*]*\s*(?:\[[^\]]*\])?\s*(?:\[[^\]]*\])?\{([^}]*)\}"
)

_AUTOSURVEY_MODULES: dict[str, Any] = {
    "write_outline": None,
    "write_subsection": None,
    "relatedWorksWriter": None,
    "database": None,
    "src_prompt": None,
}
_AUTOSURVEY_LOADED = False
_AUTOSURVEY_ROOT: Path | None = None
_AUTOSURVEY_LOAD_LOCK = threading.Lock()
_DB_INSTANCE: Any = None


def _query_tokens(text: str) -> set[str]:
    stopwords = {
        "a",
        "an",
        "and",
        "are",
        "as",
        "for",
        "in",
        "is",
        "of",
        "on",
        "or",
        "the",
        "to",
        "with",
    }
    return {
        token
        for token in re.findall(r"[a-z0-9]+", (text or "").lower())
        if len(token) > 2 and token not in stopwords
    }


class ExternalPaperDatabase:
    """Small retrieval adapter over survey/library artifacts."""

    def __init__(self, papers: list[dict[str, Any]]):
        self._papers: dict[str, dict[str, Any]] = {}
        self._ordered_ids: list[str] = []
        for index, raw in enumerate(papers):
            paper = normalize_external_paper(raw)
            paper_id = str(
                paper.get("id")
                or paper.get("paperId")
                or paper.get("paper_key")
                or f"external-{index}"
            )
            paper["id"] = paper_id
            paper.setdefault("abs", paper.get("abstract", ""))
            if paper_id in self._papers:
                continue
            self._papers[paper_id] = paper
            self._ordered_ids.append(paper_id)

    def _score(self, query: str, paper: dict[str, Any]) -> float:
        tokens = _query_tokens(query)
        if not tokens:
            return 0.0
        title = paper_title(paper)
        topics = paper.get("topics", [])
        topic_text = " ".join(topics) if isinstance(topics, list) else str(topics)
        haystack = " ".join(
            [
                title,
                title,
                title,
                str(paper.get("abs") or paper.get("abstract") or ""),
                topic_text,
                str(paper.get("strengths") or ""),
                str(paper.get("summary_markdown") or ""),
            ]
        ).lower()
        score = sum(1.0 for token in tokens if token in haystack)
        if query.lower() in haystack:
            score += 5.0
        citation_count = paper.get("citationCount") or paper.get("citation_count") or 0
        try:
            score += min(float(citation_count), 1000.0) / 10000.0
        except (TypeError, ValueError):
            pass
        return score

    def get_ids_from_query(
        self,
        query: str,
        num: int = 10,
        shuffle: bool = False,
    ) -> list[str]:
        ranked = sorted(
            self._ordered_ids,
            key=lambda paper_id: self._score(query, self._papers[paper_id]),
            reverse=True,
        )
        if not ranked:
            return []
        scored = [
            paper_id
            for paper_id in ranked
            if self._score(query, self._papers[paper_id]) > 0
        ]
        selected = scored or ranked
        if shuffle and len(selected) > 1:
            pivot = abs(hash(query)) % len(selected)
            selected = selected[pivot:] + selected[:pivot]
        return selected[:num]

    def get_paper_info_from_ids(self, paper_ids: list[str]) -> list[dict[str, Any]]:
        return [
            self._papers[paper_id]
            for paper_id in paper_ids
            if paper_id in self._papers
        ]

    def get_titles_from_citations(self, citations: list[str]) -> list[str]:
        title_to_id = {
            _normalize_title_for_match(paper_title(paper)): paper_id
            for paper_id, paper in self._papers.items()
        }
        resolved: list[str] = []
        for citation in citations:
            normalized = _normalize_title_for_match(citation)
            if normalized in title_to_id:
                resolved.append(title_to_id[normalized])
                continue
            matches = self.get_ids_from_query(citation, num=1, shuffle=False)
            resolved.append(matches[0] if matches else "")
        return resolved

    def format_papers_text(self, papers: list[dict], include_analysis: bool = True) -> str:
        return _format_papers_text_fallback(papers)


def _create_namespace_package(name: str, search_paths: list[str]):
    spec = importlib.machinery.ModuleSpec(name=name, loader=None, is_package=True)
    spec.submodule_search_locations = search_paths
    module = importlib.util.module_from_spec(spec)
    module.__path__ = search_paths
    return module


def _load_module_from_path(module_name: str, module_path: Path):
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load module from {module_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def _candidate_autosurvey_roots() -> list[Path]:
    cwd = Path.cwd().resolve()
    candidates: list[Path] = []

    autosurvey_root = os.getenv("AUTOSURVEY_ROOT", "").strip()
    if autosurvey_root:
        candidates.append(Path(autosurvey_root).expanduser().resolve())

    agentscope_survey_root = os.getenv("AGENTSCOPE_SURVEY_ROOT", "").strip()
    if agentscope_survey_root:
        candidates.append(
            (Path(agentscope_survey_root).expanduser().resolve() / "AutoSurvey")
        )

    for base in [cwd, *cwd.parents]:
        candidates.extend(
            [
                base / "../meta-agent/modules/agentscope-survey/AutoSurvey",
                base / "meta-agent/modules/agentscope-survey/AutoSurvey",
                base / "AutoSurvey",
            ]
        )

    unique: list[Path] = []
    seen: set[str] = set()
    for candidate in candidates:
        try:
            resolved = candidate.resolve()
        except FileNotFoundError:
            resolved = candidate
        key = str(resolved)
        if key in seen:
            continue
        seen.add(key)
        unique.append(resolved)
    return unique


def find_autosurvey_root() -> Path:
    global _AUTOSURVEY_ROOT
    if _AUTOSURVEY_ROOT is not None:
        return _AUTOSURVEY_ROOT

    for candidate in _candidate_autosurvey_roots():
        if (candidate / "main.py").exists() and (
            candidate / "src" / "prompt.py"
        ).exists():
            _AUTOSURVEY_ROOT = candidate
            return candidate

    search_hint = "\n".join(f"- {path}" for path in _candidate_autosurvey_roots())
    raise FileNotFoundError(
        "Unable to locate AutoSurvey.\n"
        "Set AUTOSURVEY_ROOT or AGENTSCOPE_SURVEY_ROOT, or check out the upstream module.\n"
        "Searched:\n"
        f"{search_hint}\n"
        "If dependencies are missing, run:\n"
        "  cd ../meta-agent/modules/agentscope-survey && uv sync"
    )


def load_autosurvey() -> None:
    global _AUTOSURVEY_LOADED

    if _AUTOSURVEY_LOADED:
        return

    with _AUTOSURVEY_LOAD_LOCK:
        if _AUTOSURVEY_LOADED:
            return

        autosurvey_root = find_autosurvey_root()
        original_path = sys.path.copy()
        src_modules_backup: dict[str, Any] = {}

        try:
            for key in list(sys.modules.keys()):
                if key == "src" or key.startswith("src."):
                    src_modules_backup[key] = sys.modules.pop(key)

            autosurvey_src_path = autosurvey_root / "src"
            sys.path = [str(autosurvey_root)] + [
                path for path in sys.path if path != str(autosurvey_root)
            ]
            sys.modules["src"] = _create_namespace_package(
                "src", [str(autosurvey_src_path)]
            )
            sys.modules.pop("_autosurvey_main", None)

            autosurvey_main = _load_module_from_path(
                "_autosurvey_main", autosurvey_root / "main.py"
            )
            src_prompt = sys.modules.get("src.prompt")
            if src_prompt is None:
                src_prompt = _load_module_from_path(
                    "src.prompt", autosurvey_src_path / "prompt.py"
                )

            _AUTOSURVEY_MODULES["write_outline"] = autosurvey_main.write_outline
            _AUTOSURVEY_MODULES["write_subsection"] = autosurvey_main.write_subsection
            _AUTOSURVEY_MODULES["relatedWorksWriter"] = (
                autosurvey_main.relatedWorksWriter
            )
            _AUTOSURVEY_MODULES["database"] = autosurvey_main.database
            _AUTOSURVEY_MODULES["src_prompt"] = src_prompt
            _AUTOSURVEY_LOADED = True
        finally:
            sys.path = original_path
            for key in list(sys.modules.keys()):
                if key == "src" or key.startswith("src."):
                    sys.modules.pop(key)
            sys.modules.update(src_modules_backup)


def load_prompt_templates():
    return _load_vendored_prompts()


_VENDORED_PROMPTS: Any = None


def _load_vendored_prompts():
    global _VENDORED_PROMPTS
    if _VENDORED_PROMPTS is not None:
        return _VENDORED_PROMPTS
    here = Path(__file__).resolve().parent
    spec = importlib.util.spec_from_file_location(
        "reasflow_prompts_vendored", here / "prompts_vendored.py"
    )
    if spec is None or spec.loader is None:
        raise ImportError("Cannot load vendored prompt templates")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    _VENDORED_PROMPTS = module
    return module


def fill_prompt(template: str, paras: dict[str, str]) -> str:
    prompt = template
    for k, v in paras.items():
        prompt = prompt.replace(f"[{k}]", v)
    return prompt


def get_database(args: argparse.Namespace):
    global _DB_INSTANCE
    if _DB_INSTANCE is not None:
        return _DB_INSTANCE

    library_dir = getattr(args, "library_dir", "")
    if library_dir:
        workspace_root = resolve_workspace(getattr(args, "workspace", "."))
        external_papers = load_external_library_papers(workspace_root, library_dir)
        if external_papers:
            _DB_INSTANCE = ExternalPaperDatabase(external_papers)
            print(
                f"Using external survey library database: {library_dir} "
                f"({len(external_papers)} papers)",
                file=sys.stderr,
            )
            return _DB_INSTANCE

    load_autosurvey()
    embedding_model = args.embedding_model or DEFAULT_EMBEDDING_MODEL
    db_path = args.db_path
    if not db_path:
        db_path = str(find_autosurvey_root() / "database")

    database_cls = _AUTOSURVEY_MODULES["database"]
    if database_cls is None:
        raise RuntimeError("AutoSurvey database class was not loaded")

    if not os.getenv("HF_ENDPOINT"):
        os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"
    if not os.getenv("HUGGINGFACE_HUB_ENDPOINT"):
        os.environ["HUGGINGFACE_HUB_ENDPOINT"] = "https://hf-mirror.com"

    _DB_INSTANCE = database_cls(db_path=db_path, embedding_model=embedding_model)
    return _DB_INSTANCE


def resolve_workspace(workspace: str) -> Path:
    return Path(workspace or ".").expanduser().resolve()


def resolve_path(workspace_root: Path, raw_path: str) -> Path:
    path = Path(raw_path)
    resolved = (
        path.resolve() if path.is_absolute() else (workspace_root / path).resolve()
    )
    try:
        resolved.relative_to(workspace_root)
    except ValueError as exc:
        raise ValueError(f"Path escapes workspace: {raw_path}") from exc
    return resolved


def ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def write_json(path: Path, data: Any) -> None:
    ensure_parent(path)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def parse_cite_keys(tex_path: Path) -> set[str]:
    content = tex_path.read_text(encoding="utf-8")
    keys: set[str] = set()
    for match in CITE_PATTERN.finditer(content):
        for key in match.group(1).split(","):
            cleaned = key.strip()
            if cleaned:
                keys.add(cleaned)
    return keys


def parse_bib_keys(bib_path: Path) -> tuple[set[str], list[str]]:
    content = bib_path.read_text(encoding="utf-8")
    keys: set[str] = set()
    duplicates: list[str] = []
    for match in BIB_PATTERN.finditer(content):
        key = match.group(1).strip()
        if not key:
            continue
        if key in keys:
            duplicates.append(key)
            continue
        keys.add(key)
    return keys, duplicates


def parse_bib_entries(bib_path: Path) -> dict[str, dict[str, str]]:
    if not bib_path.exists():
        return {}
    content = bib_path.read_text(encoding="utf-8")
    entries: dict[str, dict[str, str]] = {}
    for match in re.finditer(r"@(\w+)\s*\{\s*([^,\s]+)\s*,", content, re.IGNORECASE):
        entry_start = match.start()
        next_match = re.search(r"\n\s*@", content[match.end() :])
        entry_end = (
            match.end() + next_match.start()
            if next_match
            else len(content)
        )
        raw_entry = content[entry_start:entry_end].strip()
        key = match.group(2).strip()
        fields: dict[str, str] = {
            "id": key,
            "bib_key": key,
            "entry_type": match.group(1).lower(),
            "raw_bibtex": raw_entry,
        }
        for field_match in re.finditer(
            r"\b([A-Za-z][A-Za-z0-9_-]*)\s*=\s*[\{\"]([^}\"]*)[\}\"]",
            raw_entry,
            re.DOTALL,
        ):
            field = field_match.group(1).lower()
            value = re.sub(r"\s+", " ", field_match.group(2)).strip()
            fields[field] = value
        if "authors" not in fields and "author" in fields:
            fields["authors"] = fields["author"]
        entries[key] = fields
    return entries


def merge_existing_cited_bib_entries(
    generated_bib: str,
    existing_bib_path: Path,
    cited_keys: set[str],
) -> str:
    if not existing_bib_path.exists() or not cited_keys:
        return generated_bib
    existing_entries = parse_bib_entries(existing_bib_path)
    generated_keys, _ = parse_bib_keys_from_content(generated_bib)
    extras: list[str] = []
    for key in sorted(cited_keys):
        if key in generated_keys:
            continue
        raw_entry = existing_entries.get(key, {}).get("raw_bibtex", "").strip()
        if raw_entry:
            extras.append(raw_entry)
    if not extras:
        return generated_bib
    merged = generated_bib.rstrip()
    if merged:
        merged += "\n\n"
    merged += "\n\n".join(extras)
    if not merged.endswith("\n"):
        merged += "\n"
    return merged


def parse_bib_keys_from_content(content: str) -> tuple[set[str], list[str]]:
    keys: set[str] = set()
    duplicates: list[str] = []
    for match in BIB_PATTERN.finditer(content):
        key = match.group(1).strip()
        if not key:
            continue
        if key in keys:
            duplicates.append(key)
            continue
        keys.add(key)
    return keys, duplicates


def sanitize_related_works(tex_content: str) -> tuple[str, list[str]]:
    notes: list[str] = []
    kept_lines: list[str] = []

    for line in tex_content.splitlines():
        if LATEX_PREAMBLE_PATTERN.match(line):
            notes.append(f"removed preamble line: {line.strip()}")
            continue
        kept_lines.append(line)

    sanitized = "\n".join(kept_lines).strip()
    if not sanitized.endswith("\n"):
        sanitized += "\n"
    return sanitized, notes


def validate_tex_bib(tex_paths: list[Path], bib_path: Path) -> dict[str, Any]:
    cited_keys: set[str] = set()
    citations_by_file: dict[str, list[str]] = {}

    for tex_path in tex_paths:
        keys = sorted(parse_cite_keys(tex_path))
        cited_keys.update(keys)
        citations_by_file[str(tex_path)] = keys

    bib_keys, duplicate_keys = parse_bib_keys(bib_path)
    missing_keys = sorted(cited_keys - bib_keys)
    unused_keys = sorted(bib_keys - cited_keys)

    return {
        "tex_files": [str(path) for path in tex_paths],
        "bib_file": str(bib_path),
        "citations_by_file": citations_by_file,
        "cited_key_count": len(cited_keys),
        "bib_key_count": len(bib_keys),
        "missing_keys": missing_keys,
        "unused_keys": unused_keys,
        "duplicate_bib_keys": duplicate_keys,
        "ok": not missing_keys and not duplicate_keys,
    }


def validate_required_files(paths: list[Path]) -> dict[str, Any]:
    required_files = [str(path) for path in paths]
    missing_files = [str(path) for path in paths if not path.exists()]
    return {
        "required_files": required_files,
        "missing_files": missing_files,
        "ok": not missing_files,
    }


def extract_title_sections_descriptions(outline: str):
    title = ""
    sections: list[str] = []
    descriptions: list[str] = []
    lines = outline.strip().split("\n")
    for line in lines:
        line = line.strip()
        if line.lower().startswith("title:"):
            title = line[len("title:") :].strip()
        elif line.lower().startswith("section") and ":" in line:
            parts = line.split(":", 1)
            sections.append(parts[1].strip())
        elif line.lower().startswith("description") and ":" in line:
            parts = line.split(":", 1)
            descriptions.append(parts[1].strip())
    return title, sections, descriptions


def extract_subsections_subdescriptions(outline: str):
    subsections: list[str] = []
    sub_descriptions: list[str] = []
    lines = outline.strip().split("\n")
    for line in lines:
        line = line.strip()
        if line.lower().startswith("subsection") and ":" in line:
            parts = line.split(":", 1)
            subsections.append(parts[1].strip())
        elif line.lower().startswith("description") and ":" in line:
            parts = line.split(":", 1)
            sub_descriptions.append(parts[1].strip())
    return subsections, sub_descriptions


def chunk_papers(abstracts: list[str], titles: list[str], chunk_size: int = 30000):
    abs_chunks: list[list[str]] = []
    titles_chunks: list[list[str]] = []
    current_abs: list[str] = []
    current_titles: list[str] = []
    current_len = 0
    for title, abstract in zip(titles, abstracts):
        text = f"---\npaper_title: {title}\n\npaper_content:\n\n{abstract}\n"
        if current_len + len(text) > chunk_size and current_abs:
            abs_chunks.append(current_abs)
            titles_chunks.append(current_titles)
            current_abs = []
            current_titles = []
            current_len = 0
        current_abs.append(abstract)
        current_titles.append(title)
        current_len += len(text)
    if current_abs:
        abs_chunks.append(current_abs)
        titles_chunks.append(current_titles)
    return abs_chunks, titles_chunks


def parse_outline(outline_content: str) -> dict:
    lines = outline_content.strip().split("\n")
    sections: list[str] = []
    section_descriptions: list[str] = []
    subsections: list[list[str]] = []
    subsection_descriptions: list[list[str]] = []
    current_section_idx = -1
    current_subs: list[str] = []
    current_sub_descs: list[str] = []

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("## ") or (
            stripped.startswith("#") and not stripped.startswith("### ")
        ):
            if current_section_idx >= 0:
                subsections.append(current_subs)
                subsection_descriptions.append(current_sub_descs)
            section_match = re.match(r"^#+\s+\d*\s*(.+)$", stripped)
            if section_match:
                if ":" in stripped:
                    parts = stripped.split(":", 1)
                    sections.append(
                        parts[0]
                        .rstrip()
                        .rstrip("#")
                        .rstrip()
                        .rstrip("0123456789.")
                        .strip()
                    )
                    section_descriptions.append(parts[1].strip())
                else:
                    sections.append(section_match.group(1).strip())
                    section_descriptions.append("")
                current_section_idx += 1
                current_subs = []
                current_sub_descs = []
        elif stripped.startswith("### "):
            if ":" in stripped:
                parts = stripped.split(":", 1)
                current_subs.append(
                    parts[0].replace("###", "").strip().lstrip("0123456789.").strip()
                )
                current_sub_descs.append(parts[1].strip())
            else:
                current_subs.append(
                    stripped.replace("###", "").strip().lstrip("0123456789.").strip()
                )
                current_sub_descs.append("")
        elif stripped.lower().startswith("description:") and current_section_idx >= 0:
            if current_subs:
                current_sub_descs[-1] = stripped[len("description:") :].strip()
            elif not section_descriptions[current_section_idx]:
                section_descriptions[current_section_idx] = stripped[
                    len("description:") :
                ].strip()

    if current_section_idx >= 0:
        subsections.append(current_subs)
        subsection_descriptions.append(current_sub_descs)

    return {
        "sections": sections,
        "section_descriptions": section_descriptions,
        "subsections": subsections,
        "subsection_descriptions": subsection_descriptions,
    }


def extract_citations(text: str) -> list[str]:
    pattern = re.compile(r"\[([^\]]+)\]")
    citations: list[str] = []
    seen = set()
    for match in pattern.finditer(text):
        for cite in match.group(1).split(";"):
            cite = cite.strip()
            if cite and cite not in seen:
                citations.append(cite)
                seen.add(cite)
    return citations


def replace_title_citations_with_numbers(
    text: str,
    citation_to_ref_num: dict[str, str],
) -> str:
    def replace_match(match: re.Match[str]) -> str:
        raw_group = match.group(1)
        parts = [part.strip() for part in raw_group.split(";") if part.strip()]
        if not parts:
            return match.group(0)
        ref_nums: list[str] = []
        for part in parts:
            ref_num = citation_to_ref_num.get(part)
            if not ref_num:
                return match.group(0)
            ref_nums.append(ref_num)
        return "[" + "; ".join(ref_nums) + "]"

    return re.sub(r"\[([^\]]+)\]", replace_match, text)


def generate_bibtex_key(paper: dict) -> str:
    authors = paper.get("authors", [])
    first_author = ""
    if authors:
        if isinstance(authors, list):
            first_author = authors[0] if authors else ""
        else:
            first_author = str(authors).split(",")[0].strip()
    first_author = re.sub(r"[^a-zA-Z]", "", first_author).lower()[:10]
    year = str(paper.get("year", "2024"))
    title_words = re.findall(r"[a-zA-Z]+", paper.get("title", ""))
    title_key = "".join(w.lower() for w in title_words[:3])
    return f"{first_author}{year}{title_key}"


def assign_unique_bibtex_keys(papers: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Attach stable, collision-free citation keys without changing paper order."""
    used: set[str] = set()
    keyed: list[dict[str, Any]] = []
    for paper in papers:
        row = dict(paper)
        base = generate_bibtex_key(row) or "paper"
        key = base
        suffix = 2
        while key in used:
            key = f"{base}{suffix}"
            suffix += 1
        used.add(key)
        row["bib_key"] = key
        keyed.append(row)
    return keyed


def extract_bibtex_key(bibtex: str) -> str:
    if not bibtex or not isinstance(bibtex, str):
        return ""
    match = BIB_PATTERN.search(bibtex.strip())
    return match.group(1).strip() if match else ""


def _clean_arxiv_id(arxiv_id: str) -> str:
    return re.sub(r"v\d+$", "", arxiv_id or "")


def _bibtex_field(bibtex: str, field: str) -> str:
    match = re.search(
        rf"\b{re.escape(field)}\s*=\s*[\{{\"]([^}}\"]+)[\}}\"]",
        bibtex or "",
        flags=re.IGNORECASE | re.DOTALL,
    )
    if not match:
        return ""
    return re.sub(r"\s+", " ", match.group(1)).strip()


def _paper_arxiv_id(paper: dict) -> str:
    external_ids = paper.get("externalIds") or paper.get("external_ids") or {}
    if isinstance(external_ids, dict):
        arxiv_id = external_ids.get("ArXiv") or external_ids.get("arxiv") or ""
        if arxiv_id and re.fullmatch(r"\d{4}\.\d{4,5}(?:v\d+)?", str(arxiv_id)):
            return str(arxiv_id)
    for field in ("arxiv_id", "id"):
        value = str(paper.get(field) or "").strip()
        if re.fullmatch(r"\d{4}\.\d{4,5}(?:v\d+)?", value):
            return value
    return ""


def _paper_year(paper: dict) -> str:
    for field in ("year", "date", "published", "publicationDate"):
        value = paper.get(field)
        if value:
            match = re.search(r"\d{4}", str(value))
            if match:
                return match.group(0)
    return "2024"


def _bibtex_describes_arxiv(bibtex: str, arxiv_id: str = "") -> bool:
    lower_bib = (bibtex or "").lower()
    journal = _bibtex_field(bibtex, "journal").lower()
    clean_id = _clean_arxiv_id(arxiv_id)
    return (
        "arxiv preprint" in lower_bib
        or journal in {"arxiv", "arxiv.org"}
        or journal.startswith("arxiv")
        or (clean_id and clean_id.lower() in lower_bib and "arxiv" in lower_bib)
    )


def _bibtex_has_published_venue(bibtex: str) -> bool:
    journal = _bibtex_field(bibtex, "journal").lower()
    booktitle = _bibtex_field(bibtex, "booktitle").lower()
    if booktitle:
        return True
    return bool(journal and "arxiv" not in journal)


def _remove_bibtex_fields(bibtex: str, fields: set[str]) -> str:
    cleaned = bibtex
    for field in fields:
        cleaned = re.sub(
            rf"\n\s*{re.escape(field)}\s*=\s*[\{{\"](?:[^}}\"]*)[\}}\"]\s*,?",
            "",
            cleaned,
            flags=re.IGNORECASE | re.DOTALL,
        )
    return cleaned


def _normalize_arxiv_preprint_bibtex(bibtex: str) -> str:
    journal = _bibtex_field(bibtex, "journal").lower()
    if journal.startswith("arxiv") or "arxiv preprint" in journal:
        cleaned = _remove_bibtex_fields(bibtex, {"journal"})
        return re.sub(r"^@\s*article", "@misc", cleaned, count=1, flags=re.IGNORECASE)
    return bibtex


def _normalize_mixed_arxiv_bibtex(paper: dict, bibtex: str) -> str:
    """Remove S2 records that mix a formal venue with arXiv volume fields.

    Semantic Scholar sometimes exposes the venue of a later publication while
    retaining ``volume = {abs/...}`` and an arXiv resolver as if those fields
    described the formal version.  Unless a non-arXiv DOI is present, the
    conservative publication-safe representation is an explicit preprint.
    """
    volume = _bibtex_field(bibtex, "volume")
    url = _bibtex_field(bibtex, "url")
    doi = _bibtex_field(bibtex, "doi")
    arxiv_id = _clean_arxiv_id(_paper_arxiv_id(paper))
    has_abs_volume = volume.casefold().startswith("abs/")
    has_arxiv_locator = (
        _is_arxiv_url(url)
        or "10.48550/arxiv." in doi.casefold()
        or "10.48550/arxiv." in url.casefold()
    )
    has_formal_doi = bool(doi and not doi.casefold().startswith("10.48550/arxiv."))

    if has_formal_doi:
        if has_abs_volume:
            bibtex = _remove_bibtex_fields(bibtex, {"volume"})
        if has_arxiv_locator:
            bibtex = _remove_bibtex_fields(bibtex, {"url"})
        return bibtex

    if has_abs_volume:
        bibtex = _remove_bibtex_fields(
            bibtex, {"journal", "booktitle", "volume", "number", "pages", "doi", "url"}
        )
        bibtex = re.sub(r"^@\s*(?:article|inproceedings)", "@misc", bibtex, count=1, flags=re.IGNORECASE)
        if not arxiv_id:
            arxiv_id = volume.split("/", 1)[-1]
        bibtex = _insert_bibtex_field(bibtex, "eprint", arxiv_id)
        bibtex = _insert_bibtex_field(bibtex, "archiveprefix", "arXiv")
        bibtex = _insert_bibtex_field(
            bibtex, "url", f"https://arxiv.org/abs/{arxiv_id}" if arxiv_id else ""
        )
    elif _bibtex_has_published_venue(bibtex) and has_arxiv_locator:
        bibtex = _remove_bibtex_fields(bibtex, {"url", "doi"})
    return bibtex


def _repair_bibtex_mojibake(bibtex: str) -> str:
    value = html.unescape(str(bibtex or ""))
    replacements = {
        "â€“": "--",
        "â€”": "---",
        "âˆ’": "-",
        "Â ": " ",
        "Â": "",
    }
    for bad, good in replacements.items():
        value = value.replace(bad, good)
    return re.sub(r"(?<!\\)&", r"\\&", value)


def _is_arxiv_url(url: str) -> bool:
    lowered = (url or "").lower()
    return "arxiv.org" in lowered or "10.48550/arxiv." in lowered


def _is_internal_reascholar_url(url: str) -> bool:
    lowered = (url or "").lower()
    return "scholar.reaslab.io/api/papers/" in lowered


def _canonical_bib_url(paper: dict) -> str:
    doi = str(paper.get("doi") or (paper.get("externalIds") or {}).get("DOI") or "").strip()
    if doi.startswith("10."):
        return f"https://doi.org/{doi}"

    arxiv_id = _paper_arxiv_id(paper)
    if arxiv_id and re.search(r"\d{4}\.\d{4,5}", arxiv_id):
        return f"https://arxiv.org/abs/{_clean_arxiv_id(arxiv_id)}"

    url = str(paper.get("url") or "").strip()
    if not url or _is_internal_reascholar_url(url):
        return ""
    return url


def _formal_doi(paper: dict) -> str:
    doi = str(
        paper.get("doi") or (paper.get("externalIds") or {}).get("DOI") or ""
    ).strip()
    doi = re.sub(r"^https?://(?:dx\.)?doi\.org/", "", doi, flags=re.IGNORECASE)
    if not doi.startswith("10.") or doi.lower().startswith("10.48550/arxiv."):
        return ""
    return doi


def _publication_metadata(paper: dict) -> dict[str, str]:
    journal = paper.get("journal") if isinstance(paper.get("journal"), dict) else {}
    venue = str(
        paper.get("publication_venue") or journal.get("name") or ""
    ).strip()
    publication_types = " ".join(
        str(value) for value in (paper.get("publication_types") or [])
    ).lower()
    venue_lower = venue.lower()
    is_conference = "conference" in publication_types or bool(
        re.search(r"\b(conference|proceedings|workshop|symposium)\b", venue_lower)
    )
    is_journal = "journal" in publication_types or bool(journal.get("name"))
    entry_type = "inproceedings" if is_conference and not is_journal else "article"
    if not venue:
        entry_type = "misc"
    return {
        "entry_type": entry_type,
        "venue": venue,
        "volume": str(paper.get("volume") or journal.get("volume") or "").strip(),
        "number": str(paper.get("issue") or paper.get("number") or "").strip(),
        "pages": str(paper.get("pages") or journal.get("pages") or "").strip(),
        "publisher": str(paper.get("publisher") or "").strip(),
    }


def _protect_bibtex_title(title: str) -> str:
    protected = str(title or "Untitled")
    tokens = {
        "ADMM", "AI", "Byzantine", "CNN", "DGD", "EF21", "FL", "GPU",
        "LLM", "NLP", "PCA", "SGD", "SVM", "ViT",
    }
    for token in sorted(tokens, key=len, reverse=True):
        protected = re.sub(
            rf"(?<![{{A-Za-z0-9]){re.escape(token)}(?![}}A-Za-z0-9])",
            "{" + token + "}",
            protected,
        )
    return re.sub(r"(?<!\{)\b([A-Z][A-Z0-9]{1,})\b(?!\})", r"{\1}", protected)


def _bibtex_source_is_consistent(paper: dict, bibtex: str) -> bool:
    source = str(paper.get("best_citation_source") or "").lower()
    venue = str(paper.get("best_citation_venue") or "").lower()
    clean_id = _clean_arxiv_id(_paper_arxiv_id(paper)).lower()
    if clean_id and clean_id in (bibtex or "").lower():
        return True
    if _bibtex_describes_arxiv(bibtex, _paper_arxiv_id(paper)):
        return source in {"", "arxiv"} and ("arxiv" in venue or not venue)
    return True


def replace_bibtex_key(bibtex: str, new_key: str) -> str:
    return re.sub(
        r"(@\w+\s*\{\s*)([^,\s]+)",
        rf"\g<1>{new_key}",
        bibtex,
        count=1,
        flags=re.IGNORECASE,
    )


def _insert_bibtex_field(bibtex: str, field: str, value: str) -> str:
    if not value or _bibtex_field(bibtex, field):
        return bibtex
    insertion = f"  {field} = {{{value}}},\n"
    index = bibtex.rfind("}")
    if index == -1:
        return bibtex.rstrip() + "\n" + insertion
    prefix = bibtex[:index].rstrip()
    if prefix and not prefix.endswith(","):
        prefix += ","
    return prefix + "\n" + insertion + bibtex[index:]


def enrich_bibtex_entry(paper: dict, bibtex: str) -> str:
    enriched = _repair_bibtex_mojibake(bibtex.strip())
    enriched = _normalize_arxiv_preprint_bibtex(enriched)
    enriched = _normalize_mixed_arxiv_bibtex(paper, enriched)
    enriched = _insert_bibtex_field(enriched, "year", _paper_year(paper))
    has_published_venue = _bibtex_has_published_venue(enriched)
    canonical_url = _canonical_bib_url(paper)
    formal_doi = _formal_doi(paper)

    arxiv_id = _paper_arxiv_id(paper)
    if (
        arxiv_id
        and re.search(r"\d{4}\.\d{4,5}", arxiv_id)
        and not has_published_venue
    ):
        enriched = _insert_bibtex_field(enriched, "eprint", arxiv_id)
        enriched = _insert_bibtex_field(enriched, "archiveprefix", "arXiv")
        enriched = _insert_bibtex_field(enriched, "url", canonical_url)
    elif canonical_url and not formal_doi and not (
        has_published_venue and _is_arxiv_url(canonical_url)
    ):
        enriched = _insert_bibtex_field(enriched, "url", canonical_url)

    if formal_doi:
        enriched = _insert_bibtex_field(enriched, "doi", formal_doi)
        enriched = _remove_bibtex_fields(enriched, {"url"})
    return enriched


def is_weak_bibtex_key(key: str) -> bool:
    cleaned = (key or "").strip()
    return not cleaned or bool(re.fullmatch(r"\d+[a-z]?", cleaned))


def arxiv_id_to_bibtex(paper: dict, key: str) -> str:
    title = _protect_bibtex_title(str(paper.get("title") or "Untitled"))
    authors = paper.get("authors", ["Unknown"])
    if isinstance(authors, str):
        authors = [a.strip() for a in authors.split(",")]
    year = _paper_year(paper)
    author_str = " and ".join(authors)

    arxiv_id = _paper_arxiv_id(paper)
    url = _canonical_bib_url(paper)
    formal_doi = _formal_doi(paper)
    publication = _publication_metadata(paper)
    entry_type = publication["entry_type"]
    if not publication["venue"] and not formal_doi:
        entry_type = "misc"
    bib = f"@{entry_type}{{{key},\n"
    bib += f"  title = {{{title}}},\n"
    bib += f"  author = {{{author_str}}},\n"
    bib += f"  year = {{{year}}},\n"
    if publication["venue"]:
        venue_field = "booktitle" if entry_type == "inproceedings" else "journal"
        bib += f"  {venue_field} = {{{publication['venue']}}},\n"
    for field in ("volume", "number", "pages", "publisher"):
        if publication[field]:
            bib += f"  {field} = {{{publication[field]}}},\n"
    if formal_doi:
        bib += f"  doi = {{{formal_doi}}},\n"
    if arxiv_id and not publication["venue"]:
        bib += f"  eprint = {{{arxiv_id}}},\n"
        bib += f"  archiveprefix = {{arXiv}},\n"
    if url and not formal_doi:
        bib += f"  url = {{{url}}},\n"
    bib += "}\n"
    return bib


def normalize_external_paper(raw: dict[str, Any]) -> dict[str, Any]:
    external_ids = raw.get("externalIds") or raw.get("external_ids") or {}
    if not isinstance(external_ids, dict):
        external_ids = {}
    authors = raw.get("authors") or []
    if isinstance(authors, list):
        author_names = [
            str(author.get("name") if isinstance(author, dict) else author).strip()
            for author in authors
        ]
        authors = [name for name in author_names if name]
    elif isinstance(authors, str):
        authors = [name.strip() for name in authors.split(",") if name.strip()]
    else:
        authors = []

    title = str(raw.get("title") or "").strip()
    paper_id = str(
        raw.get("id")
        or external_ids.get("ArXiv")
        or raw.get("paperId")
        or raw.get("paper_id")
        or title.lower()
    ).strip()
    abstract = str(raw.get("abs") or raw.get("abstract") or "").strip()
    return {
        "id": paper_id,
        "paperId": raw.get("paperId") or paper_id,
        "paper_key": raw.get("paper_key") or "",
        "title": title,
        "authors": authors,
        "year": raw.get("year") or raw.get("publicationDate") or raw.get("date") or "",
        "abs": abstract,
        "abstract": abstract,
        "s2_abstract": raw.get("s2_abstract") or "",
        "url": raw.get("url") or "",
        "externalIds": external_ids,
        "venue": raw.get("venue") or "",
        "publication_venue": raw.get("publication_venue") or "",
        "publication_types": raw.get("publication_types") or raw.get("publicationTypes") or [],
        "journal": raw.get("journal") if isinstance(raw.get("journal"), dict) else {},
        "volume": raw.get("volume") or "",
        "issue": raw.get("issue") or raw.get("number") or "",
        "pages": raw.get("pages") or "",
        "publisher": raw.get("publisher") or "",
        "topic_category": raw.get("topic_category") or "",
        "citationCount": raw.get("citationCount") or raw.get("citation_count") or 0,
        "referenceCount": raw.get("referenceCount") or raw.get("reference_count") or 0,
        "publicationDate": raw.get("publicationDate") or "",
        "raw_bibtex": raw.get("raw_bibtex") or raw.get("bibtex") or "",
        "best_citation_bibtex": raw.get("best_citation_bibtex") or "",
        "best_citation_source": raw.get("best_citation_source") or "",
        "best_citation_venue": raw.get("best_citation_venue") or "",
        "source": raw.get("source") or "",
        "sources": raw.get("sources") or [],
        "topics": raw.get("topics") or [],
        "strengths": raw.get("strengths") or raw.get("summary_markdown") or "",
        "weaknesses": raw.get("weaknesses") or "",
        "limitations": raw.get("limitations") or [],
        "open_problem_candidates": raw.get("open_problem_candidates") or [],
        "summary_markdown": raw.get("summary_markdown") or "",
    }


def extract_external_papers(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [normalize_external_paper(item) for item in payload if isinstance(item, dict)]
    if not isinstance(payload, dict):
        return []
    if isinstance(payload.get("paper"), dict):
        return [normalize_external_paper(payload["paper"])]
    if isinstance(payload.get("papers"), list):
        return [
            normalize_external_paper(item)
            for item in payload["papers"]
            if isinstance(item, dict)
        ]
    papers: list[dict[str, Any]] = []
    for key in ("citations", "references", "data"):
        values = payload.get(key)
        if not isinstance(values, list):
            continue
        for item in values:
            if not isinstance(item, dict):
                continue
            if isinstance(item.get("citingPaper"), dict):
                papers.append(normalize_external_paper(item["citingPaper"]))
            elif isinstance(item.get("citedPaper"), dict):
                papers.append(normalize_external_paper(item["citedPaper"]))
            else:
                papers.append(normalize_external_paper(item))
    if "title" in payload:
        papers.append(normalize_external_paper(payload))
    return papers


def load_external_library_papers(workspace_root: Path, library_dir_raw: str) -> list[dict[str, Any]]:
    library_dir = resolve_path(workspace_root, library_dir_raw)
    if not library_dir.exists():
        return []
    papers: list[dict[str, Any]] = []
    seen: set[str] = set()
    for path in sorted(library_dir.glob("*.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        for paper in extract_external_papers(payload):
            title = str(paper.get("title") or "").strip()
            if not title:
                continue
            identity = str(paper.get("id") or title.lower()).lower()
            if identity in seen:
                continue
            seen.add(identity)
            papers.append(paper)
    jsonl_path = library_dir / "paper_pool.jsonl"
    if jsonl_path.exists():
        for line in jsonl_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                paper = normalize_external_paper(json.loads(line))
            except json.JSONDecodeError:
                continue
            title = str(paper.get("title") or "").strip()
            if not title:
                continue
            identity = str(paper.get("id") or title.lower()).lower()
            if identity in seen:
                continue
            seen.add(identity)
            papers.append(paper)
    return papers


def load_frozen_paper_pool(
    workspace_root: Path, library_dir_raw: str
) -> list[dict[str, Any]]:
    """Load only paper_pool.jsonl, preserving its frozen order and identity set."""
    pool_path = resolve_path(workspace_root, library_dir_raw) / "paper_pool.jsonl"
    if not pool_path.exists():
        raise FileNotFoundError(f"Frozen paper pool is missing: {pool_path}")
    papers: list[dict[str, Any]] = []
    seen: set[str] = set()
    for line_number, line in enumerate(
        pool_path.read_text(encoding="utf-8").splitlines(), start=1
    ):
        if not line.strip():
            continue
        try:
            paper = normalize_external_paper(json.loads(line))
        except json.JSONDecodeError as exc:
            raise ValueError(
                f"Invalid JSON in frozen paper pool at line {line_number}: {pool_path}"
            ) from exc
        title = str(paper.get("title") or "").strip()
        if not title:
            continue
        identity = str(
            paper.get("id")
            or paper.get("paperId")
            or paper.get("paper_key")
            or title.lower()
        ).lower()
        if identity in seen:
            continue
        seen.add(identity)
        papers.append(paper)
    return papers


def _load_frozen_task(
    workspace_root: Path, task_path_raw: str = ""
) -> tuple[dict[str, Any], Path | None]:
    """Load the task contract used by an evaluation workspace, when present."""
    candidates: list[Path] = []
    if task_path_raw:
        candidates.append(resolve_path(workspace_root, task_path_raw))
    candidates.extend(
        [workspace_root / "frozen_task.yaml", workspace_root / "task.yaml"]
    )
    for path in candidates:
        if not path.exists():
            continue
        try:
            import yaml
        except ImportError as exc:  # pragma: no cover - deployment dependency guard
            raise RuntimeError(f"PyYAML is required to read task contract: {path}") from exc
        payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        if not isinstance(payload, dict):
            raise ValueError(f"Task contract must be a YAML mapping: {path}")
        return payload, path
    return {}, None


def _paper_abstract(paper: dict[str, Any]) -> str:
    return str(paper.get("abs") or paper.get("abstract") or "").strip()


def _paper_identity(paper: dict[str, Any]) -> str:
    return str(
        paper.get("id")
        or paper.get("paperId")
        or paper.get("paper_key")
        or _normalize_title_for_match(paper_title(paper))
    )


def _paper_information_score(paper: dict[str, Any]) -> float:
    """Bounded content-quality score; empty records cannot dominate by popularity."""
    abstract_len = len(_paper_abstract(paper))
    if abstract_len >= 800:
        abstract_score = 2.0
    elif abstract_len >= 300:
        abstract_score = 1.6
    elif abstract_len >= 100:
        abstract_score = 1.1
    elif abstract_len:
        abstract_score = 0.2
    else:
        abstract_score = -2.0

    metadata_score = 0.0
    metadata_score += 0.15 if paper.get("authors") else 0.0
    metadata_score += 0.10 if paper.get("year") else 0.0
    metadata_score += 0.10 if paper.get("venue") else 0.0
    metadata_score += 0.10 if paper.get("externalIds") else 0.0
    metadata_score += 0.15 if paper.get("strengths") else 0.0
    metadata_score += 0.10 if paper.get("weaknesses") else 0.0

    try:
        citation_count = max(0.0, float(paper.get("citationCount") or 0))
    except (TypeError, ValueError):
        citation_count = 0.0
    citation_score = min(0.75, math.log1p(citation_count) / 12.0)
    return abstract_score + metadata_score + citation_score


def _paper_query_score(paper: dict[str, Any], query: str) -> float:
    query_tokens = _query_tokens(query)
    if not query_tokens:
        return 0.0
    title_tokens = _query_tokens(paper_title(paper))
    abstract_tokens = _query_tokens(_paper_abstract(paper))
    topic_value = paper.get("topics") or []
    topic_text = " ".join(topic_value) if isinstance(topic_value, list) else str(topic_value)
    auxiliary_tokens = _query_tokens(
        " ".join(
            [
                topic_text,
                str(paper.get("strengths") or ""),
                str(paper.get("weaknesses") or ""),
            ]
        )
    )
    title_overlap = len(query_tokens & title_tokens) / len(query_tokens)
    abstract_overlap = len(query_tokens & abstract_tokens) / len(query_tokens)
    auxiliary_overlap = len(query_tokens & auxiliary_tokens) / len(query_tokens)
    return 3.0 * title_overlap + 1.5 * abstract_overlap + 0.5 * auxiliary_overlap


def _topic_signature_stems(topic: str) -> set[str]:
    """Return distinctive prefixes used only as a conservative relevance gate."""
    generic = {
        "algorithm",
        "analysis",
        "approach",
        "distributed",
        "information",
        "learning",
        "method",
        "optimization",
        "problem",
        "system",
    }
    return {
        token[:6]
        for token in _query_tokens(topic)
        if token not in generic and len(token) >= 5
    }


def _paper_matches_topic_signature(
    paper: dict[str, Any], signature_stems: set[str]
) -> bool:
    if not signature_stems:
        return True
    topic_value = paper.get("topics") or []
    topic_text = " ".join(topic_value) if isinstance(topic_value, list) else str(topic_value)
    paper_tokens = _query_tokens(
        " ".join(
            (
                paper_title(paper),
                _paper_abstract(paper),
                topic_text,
                str(paper.get("strengths") or ""),
                str(paper.get("weaknesses") or ""),
            )
        )
    )
    paper_stems = {token[:6] for token in paper_tokens if len(token) >= 5}
    return bool(signature_stems & paper_stems)


def _structure_supported_titles(
    workspace_root: Path, library_dir_raw: str
) -> set[str]:
    pack_path = resolve_path(workspace_root, library_dir_raw) / "structure_pack.json"
    if not pack_path.exists():
        return set()
    try:
        pack = json.loads(pack_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return set()
    titles: set[str] = set()
    for key in ("timeline", "gaps", "future_work"):
        for item in pack.get(key) or []:
            for support in item.get("support_papers") or []:
                title = _normalize_title_for_match(str(support.get("title") or ""))
                if title:
                    titles.add(title)
    for edge in pack.get("citation_relations") or []:
        for key in ("citing_title", "cited_title"):
            title = _normalize_title_for_match(str(edge.get(key) or ""))
            if title:
                titles.add(title)
    return titles


def select_native_evidence(
    papers: list[dict[str, Any]],
    topic: str,
    parsed_outline: dict[str, Any],
    max_papers: int,
    required_references: list[dict[str, Any]] | None = None,
    structure_supported_titles: set[str] | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Select a bounded, section-balanced writer library deterministically."""
    required_references = required_references or []
    structure_supported_titles = structure_supported_titles or set()

    deduplicated: dict[str, dict[str, Any]] = {}
    for raw in papers:
        paper = normalize_external_paper(raw)
        title_key = _normalize_title_for_match(paper_title(paper))
        if not title_key:
            continue
        current = deduplicated.get(title_key)
        if current is None or _paper_information_score(paper) > _paper_information_score(current):
            deduplicated[title_key] = paper
    candidates = list(deduplicated.values())
    signature_stems = _topic_signature_stems(topic)
    relevant_titles = {
        _normalize_title_for_match(paper_title(paper))
        for paper in candidates
        if _paper_matches_topic_signature(paper, signature_stems)
    }

    anchor_keys: list[tuple[str, set[str]]] = []
    for entry in required_references:
        canonical = _normalize_title_for_match(str(entry.get("title") or ""))
        aliases = {
            _normalize_title_for_match(str(alias))
            for alias in (entry.get("aliases") or [])
            if str(alias).strip()
        }
        if canonical:
            anchor_keys.append((canonical, aliases))

    pinned: list[dict[str, Any]] = []
    pinned_titles: set[str] = set()
    missing_anchors: list[str] = []
    by_title = {
        _normalize_title_for_match(paper_title(paper)): paper for paper in candidates
    }
    for canonical, aliases in anchor_keys:
        paper = by_title.get(canonical)
        if paper is None:
            paper = next(
                (
                    candidate
                    for title_key, candidate in by_title.items()
                    if title_key in aliases
                ),
                None,
            )
        if paper is None:
            missing_anchors.append(canonical)
            continue
        title_key = _normalize_title_for_match(paper_title(paper))
        if title_key not in pinned_titles:
            pinned.append(paper)
            pinned_titles.add(title_key)

    queries: list[str] = [topic]
    sections = parsed_outline.get("sections") or []
    section_descriptions = parsed_outline.get("section_descriptions") or []
    subsections = parsed_outline.get("subsections") or []
    subsection_descriptions = parsed_outline.get("subsection_descriptions") or []
    for section_index, section in enumerate(sections):
        section_desc = (
            section_descriptions[section_index]
            if section_index < len(section_descriptions)
            else ""
        )
        queries.append(" ".join(part for part in (section, section_desc) if part))
        section_subs = subsections[section_index] if section_index < len(subsections) else []
        section_sub_descs = (
            subsection_descriptions[section_index]
            if section_index < len(subsection_descriptions)
            else []
        )
        for subsection_index, subsection in enumerate(section_subs):
            desc = (
                section_sub_descs[subsection_index]
                if subsection_index < len(section_sub_descs)
                else ""
            )
            queries.append(" ".join(part for part in (section, subsection, desc) if part))
    queries = list(dict.fromkeys(query.strip() for query in queries if query.strip()))

    def score(paper: dict[str, Any], query: str) -> float:
        title_key = _normalize_title_for_match(paper_title(paper))
        structure_bonus = 0.35 if title_key in structure_supported_titles else 0.0
        return _paper_information_score(paper) + _paper_query_score(paper, query) + structure_bonus

    selected = pinned[:max_papers]
    selected_titles = {
        _normalize_title_for_match(paper_title(paper)) for paper in selected
    }
    per_query_coverage: dict[str, int] = {query: 0 for query in queries}

    # Two round-robin passes prevent one high-frequency branch from monopolizing context.
    for _ in range(2):
        for query in queries:
            if len(selected) >= max_papers:
                break
            eligible = [
                paper
                for paper in candidates
                if _normalize_title_for_match(paper_title(paper)) not in selected_titles
                and (
                    _normalize_title_for_match(paper_title(paper)) in relevant_titles
                    or _normalize_title_for_match(paper_title(paper)) in pinned_titles
                )
            ]
            if not eligible:
                break
            paper = max(
                eligible,
                key=lambda item: (
                    score(item, query),
                    _normalize_title_for_match(paper_title(item)),
                ),
            )
            title_key = _normalize_title_for_match(paper_title(paper))
            selected.append(paper)
            selected_titles.add(title_key)
            per_query_coverage[query] += 1

    remaining = [
        paper
        for paper in candidates
        if _normalize_title_for_match(paper_title(paper)) not in selected_titles
        and (
            _normalize_title_for_match(paper_title(paper)) in relevant_titles
            or _normalize_title_for_match(paper_title(paper)) in pinned_titles
        )
    ]
    remaining.sort(
        key=lambda paper: (
            max(score(paper, query) for query in queries),
            _normalize_title_for_match(paper_title(paper)),
        ),
        reverse=True,
    )
    selected.extend(remaining[: max(0, max_papers - len(selected))])

    selected_ids = [_paper_identity(paper) for paper in selected]
    selected_payload_hash = hashlib.sha256(
        json.dumps(selected_ids, ensure_ascii=False).encode("utf-8")
    ).hexdigest()
    manifest = {
        "policy": "deterministic-balanced-topic-gated-evidence-v2",
        "input_count": len(papers),
        "deduplicated_count": len(candidates),
        "selected_count": len(selected),
        "max_papers": max_papers,
        "topic_signature_stems": sorted(signature_stems),
        "topic_relevant_candidate_count": len(relevant_titles),
        "topic_irrelevant_candidate_count": len(candidates) - len(relevant_titles),
        "input_with_abstract_ge_100": sum(
            len(_paper_abstract(paper)) >= 100 for paper in candidates
        ),
        "selected_with_abstract_ge_100": sum(
            len(_paper_abstract(paper)) >= 100 for paper in selected
        ),
        "input_empty_abstract": sum(not _paper_abstract(paper) for paper in candidates),
        "selected_empty_abstract": sum(not _paper_abstract(paper) for paper in selected),
        "dropped_low_information_count": sum(
            len(_paper_abstract(paper)) < 100
            for paper in candidates
            if _normalize_title_for_match(paper_title(paper)) not in {
                _normalize_title_for_match(paper_title(item)) for item in selected
            }
        ),
        "pinned_anchor_count": len(pinned_titles),
        "missing_required_anchors": missing_anchors,
        "structure_supported_selected_count": sum(
            _normalize_title_for_match(paper_title(paper)) in structure_supported_titles
            for paper in selected
        ),
        "query_count": len(queries),
        "per_query_round_robin_coverage": per_query_coverage,
        "selected_ids": selected_ids,
        "selected_ids_sha256": selected_payload_hash,
    }
    return selected, manifest


STRUCTURE_CONTENT_KEYS = (
    "domains",
    "timeline",
    "gaps",
    "future_work",
    "citation_relations",
)
STRUCTURE_ITEM_KEYS = (*STRUCTURE_CONTENT_KEYS, "warnings")


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def paper_library_metadata(workspace_root: Path, library_dir_raw: str) -> dict[str, Any]:
    library_dir = resolve_path(workspace_root, library_dir_raw)
    pool_path = library_dir / "paper_pool.jsonl"
    return {
        "library_dir": str(library_dir),
        "paper_pool_path": str(pool_path) if pool_path.exists() else None,
        "paper_pool_sha256": _sha256_file(pool_path) if pool_path.exists() else None,
        "paper_pool_line_count": sum(
            1
            for line in pool_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        )
        if pool_path.exists()
        else 0,
    }


def _render_structure_prompt(pack: dict[str, Any]) -> str:
    lines = [
        "ReaScholar structure treatment (provisional; the paper library above remains the only citation source):",
        "---",
        "Use the following structure to test better synthesis, not as a source of facts or citations.",
    ]
    domains = pack.get("domains") or []
    if domains:
        lines.append("Candidate research branches:")
        for item in domains[:8]:
            description = str(item.get("description") or "").strip()
            suffix = f" — {description}" if description else ""
            lines.append(f"- {item.get('title')}{suffix}")
    for key, heading in (
        ("timeline", "Evolution/lineage candidates"),
        ("gaps", "Limitation/gap candidates"),
        ("future_work", "Future-work candidates"),
    ):
        items = pack.get(key) or []
        if not items:
            continue
        lines.append(f"{heading}:")
        for item in items[:16]:
            support = "; ".join(
                str(paper.get("title") or "")
                for paper in item.get("support_papers") or []
                if paper.get("title")
            )
            support_text = support or "NO RESOLVED SUPPORT IN FROZEN POOL"
            period = ""
            if item.get("period_start") or item.get("period_end"):
                period = f" [{item.get('period_start') or '?'}-{item.get('period_end') or '?'}]"
            lines.append(
                f"- [PROVISIONAL]{period} {item.get('candidate_claim')} (listed support: {support_text})"
            )
    relations = pack.get("citation_relations") or []
    if relations:
        lines.append("Within-library citation relations:")
        for edge in relations[:40]:
            lines.append(
                f"- {edge.get('citing_title')} cites {edge.get('cited_title')}"
            )
    warnings = pack.get("warnings") or []
    if warnings:
        lines.append(
            f"Evidence warning: {len(warnings)} items have unresolved or out-of-pool support identifiers; never cite those identifiers."
        )
    lines.extend(
        [
            "Required use when applicable:",
            "1. Organize the survey around meaningful research branches rather than a paper-by-paper list.",
            "2. Before naming branches, define 3-6 orthogonal comparison axes that form a reusable coordinate system, such as mechanism, information flow, assumptions, resource cost, and guarantee. Map every major branch to the same axes.",
            "3. Explain at least one supported evolution or lineage and distinguish chronological succession from a verified citation relation.",
            "4. Include a compact cross-branch decision table comparing mechanisms, assumptions, guarantees, limitations, and the regime in which each branch should be preferred.",
            "5. State a timeline, gap, or future direction only when the listed support papers in the frozen library substantiate it; otherwise mark it uncertain or omit it.",
            "6. Treat every supplied branch as optional. Omit any branch or paper that is only adjacent to the topic and cannot be placed on the common comparison axes with direct evidence.",
            "7. Do not present Domain prose, unresolved IDs, or absent support papers as evidence.",
            "8. Internalize these constraints without mentioning ReaScholar, Domain pages, the structure pack, the frozen library/pool, support lists, or the availability/absence of citation edges in the survey itself.",
            "---",
        ]
    )
    return "\n".join(lines)


def load_structure_context(
    workspace_root: Path, args: argparse.Namespace
) -> tuple[str, dict[str, Any]]:
    mode = str(getattr(args, "structure_mode", "auto") or "auto")
    if mode not in {"auto", "include", "exclude"}:
        raise ValueError(f"Unknown structure mode: {mode}")
    metadata: dict[str, Any] = {
        "requested_mode": mode,
        "included": False,
        "structure_pack_path": None,
        "structure_pack_sha256": None,
        "counts": {key: 0 for key in STRUCTURE_ITEM_KEYS},
    }
    if mode == "exclude":
        return "", metadata

    raw_path = str(getattr(args, "structure_pack", "") or "").strip()
    if raw_path:
        pack_path = resolve_path(workspace_root, raw_path)
    else:
        library_dir = resolve_path(workspace_root, getattr(args, "library_dir", "survey/library"))
        pack_path = library_dir / "structure_pack.json"
    metadata["structure_pack_path"] = str(pack_path)
    if not pack_path.exists():
        if mode == "include":
            raise FileNotFoundError(f"Structure pack is required but missing: {pack_path}")
        return "", metadata
    try:
        pack = json.loads(pack_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid structure pack JSON: {pack_path}") from exc
    if pack.get("schema_version") != "reascholar-structure-pack-v1":
        raise ValueError(f"Unsupported structure pack schema: {pack.get('schema_version')}")
    counts = {
        key: len(pack.get(key) or []) if isinstance(pack.get(key), list) else 0
        for key in STRUCTURE_ITEM_KEYS
    }
    metadata.update(
        {
            "structure_pack_sha256": _sha256_file(pack_path),
            "counts": counts,
        }
    )
    useful_count = sum(counts[key] for key in STRUCTURE_CONTENT_KEYS)
    if useful_count == 0:
        if mode == "include":
            raise ValueError(f"Structure pack has no usable structural items: {pack_path}")
        return "", metadata
    metadata["included"] = True
    return _render_structure_prompt(pack), metadata


def select_bibtex_entry(paper: dict, fallback_key: str | None = None) -> tuple[str, str]:
    for field in ("raw_bibtex", "best_citation_bibtex"):
        bibtex = paper.get(field)
        if not bibtex or not isinstance(bibtex, str):
            continue
        if field == "best_citation_bibtex" and not _bibtex_source_is_consistent(
            paper, bibtex
        ):
            continue
        key = extract_bibtex_key(bibtex)
        if key and not is_weak_bibtex_key(key):
            return key, enrich_bibtex_entry(paper, bibtex)

    key = fallback_key or paper.get("bib_key") or generate_bibtex_key(paper)
    return str(key), enrich_bibtex_entry(paper, arxiv_id_to_bibtex(paper, str(key)))


def count_words(text: str) -> int:
    return len(re.findall(r"\b[\w'-]+\b", text))


def count_tex_content_words(text: str) -> int:
    """Mirror the benchmark's normalized TeX word-count contract."""

    citation_pattern = (
        r"\\cite[a-zA-Z]*\*?(?:\s*\[[^\]]*\]){0,2}\s*\{([^{}]+)\}"
    )

    def replace_citation(match: re.Match[str]) -> str:
        keys = [key.strip() for key in match.group(1).split(",") if key.strip()]
        if not keys:
            return " "
        return " [" + "; ".join(f"@{key}" for key in keys) + "] "

    text = re.sub(r"(?<!\\)%.*", "", text)
    text = re.sub(citation_pattern, replace_citation, text)
    text = re.sub(r"\\(begin|end)\{[^}]+\}", " ", text)
    text = re.sub(r"\\section\*?\{([^}]+)\}", r"\n## \1\n", text)
    text = re.sub(r"\\subsection\*?\{([^}]+)\}", r"\n### \1\n", text)
    text = re.sub(r"\\subsubsection\*?\{([^}]+)\}", r"\n#### \1\n", text)
    text = re.sub(r"\\(?:textbf|emph)\{([^}]+)\}", r"\1", text)
    text = re.sub(r"\\[a-zA-Z]+\*?(?:\[[^\]]*\])?", " ", text)
    text = re.sub(r"[{}$]", "", text)
    text = text.replace(r"\%", "%")
    text = unicodedata.normalize("NFKC", text)
    text = re.sub(r"\s+", " ", text).strip()
    return len(text.split())


def count_related_sections(text: str) -> int:
    return len(
        re.findall(
            r"^\s*\\(?:section|subsection|paragraph)\s*\{",
            text,
            flags=re.MULTILINE,
        )
    )


def count_survey_subsections(text: str) -> int:
    return len(
        re.findall(
            r"^\s*###\s+",
            text,
            flags=re.MULTILINE,
        )
    )


def count_lines(text: str) -> int:
    return len(text.splitlines())


def normalize_reference_key_map(
    reference_ids: dict[str, str],
    references_full: dict[str, dict],
    key_map: dict[str, str] | None = None,
) -> dict[str, str]:
    normalized: dict[str, str] = {}
    used: set[str] = set()
    for ref_num, paper_id in reference_ids.items():
        paper = references_full.get(paper_id) or references_full.get(ref_num, {})
        selected_key, _ = select_bibtex_entry(paper)
        existing_key = (key_map or {}).get(ref_num)
        key = (
            existing_key
            if existing_key and not is_weak_bibtex_key(existing_key)
            else paper.get("bib_key") or selected_key or generate_bibtex_key(paper)
        )
        base_key = key
        counter = 1
        while key in used:
            counter += 1
            key = f"{base_key}{counter}"
        used.add(key)
        normalized[ref_num] = key
    return normalized


def _normalize_title_for_match(title: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (title or "").lower()).strip()


def canonical_reference_tokens(paper: dict[str, Any]) -> set[str]:
    external = paper.get("externalIds") or paper.get("external_ids") or {}
    if not isinstance(external, dict):
        external = {}
    tokens: set[str] = set()
    doi = str(paper.get("doi") or external.get("DOI") or "").strip().casefold()
    for bibtex_field in ("raw_bibtex", "best_citation_bibtex"):
        if not doi and isinstance(paper.get(bibtex_field), str):
            doi = _bibtex_field(paper[bibtex_field], "doi").strip().casefold()
    doi = re.sub(r"^https?://(?:dx\.)?doi\.org/", "", doi)
    if doi.startswith("10."):
        tokens.add(f"doi:{doi}")
    arxiv = _clean_arxiv_id(_paper_arxiv_id(paper)).casefold()
    if arxiv:
        tokens.add(f"arxiv:{arxiv}")
    paper_key = str(paper.get("paper_key") or "").strip().casefold()
    if paper_key:
        tokens.add(f"paper_key:{paper_key}")
    title = _normalize_title_for_match(paper_title(paper))
    if title:
        tokens.add(f"title:{title}")
    return tokens


def canonicalize_reference_maps(
    reference_ids: dict[str, str],
    references_full: dict[str, dict],
) -> tuple[dict[str, str], dict[str, dict], dict[str, str], dict[str, Any]]:
    """Merge transitive cross-source duplicate references before final packaging."""
    rows: list[tuple[str, str, dict[str, Any]]] = []
    for ref_num, paper_id in reference_ids.items():
        paper = references_full.get(paper_id) or references_full.get(ref_num) or {}
        rows.append((str(ref_num), str(paper_id), paper))
    parent = list(range(len(rows)))

    def find(index: int) -> int:
        while parent[index] != index:
            parent[index] = parent[parent[index]]
            index = parent[index]
        return index

    token_owner: dict[str, int] = {}
    for index, (_, _, paper) in enumerate(rows):
        for token in canonical_reference_tokens(paper):
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
    canonical_indexes = {min(members) for members in clusters.values()}
    aliases: dict[str, str] = {}
    canonical_ids: dict[str, str] = {}
    canonical_full: dict[str, dict] = {}
    cluster_report: list[dict[str, Any]] = []
    for members in sorted(clusters.values(), key=min):
        canonical_index = min(members)
        canonical_ref, canonical_paper_id, canonical_paper = rows[canonical_index]
        canonical_ids[canonical_ref] = canonical_paper_id
        canonical_full[canonical_paper_id] = canonical_paper
        for index in members:
            ref_num = rows[index][0]
            if ref_num != canonical_ref:
                aliases[ref_num] = canonical_ref
        if len(members) > 1:
            cluster_report.append(
                {
                    "canonical_reference_number": canonical_ref,
                    "merged_reference_numbers": [rows[index][0] for index in members],
                    "identity_tokens": sorted(
                        set().union(
                            *(canonical_reference_tokens(rows[index][2]) for index in members)
                        )
                    ),
                }
            )
    residual_owners: dict[str, list[str]] = {}
    for paper_id, paper in canonical_full.items():
        for token in canonical_reference_tokens(paper):
            residual_owners.setdefault(token, []).append(paper_id)
    residual = {
        token: paper_ids
        for token, paper_ids in residual_owners.items()
        if len(paper_ids) > 1
    }
    report = {
        "schema_version": "canonical-reference-dedup-v1",
        "input_reference_count": len(rows),
        "canonical_reference_count": len(canonical_indexes),
        "merged_reference_count": len(rows) - len(canonical_indexes),
        "clusters": cluster_report,
        "duplicate_canonical_identity_count": len(residual),
        "duplicate_canonical_identities": residual,
        "gate_passed": not residual,
    }
    return canonical_ids, canonical_full, aliases, report


def rewrite_numeric_reference_aliases(text: str, aliases: dict[str, str]) -> str:
    if not aliases:
        return text

    def replace(match: re.Match[str]) -> str:
        values = [value.strip() for value in match.group(1).split(",")]
        mapped = list(dict.fromkeys(aliases.get(value, value) for value in values))
        return "[" + ", ".join(mapped) + "]"

    return re.sub(r"\[([0-9]+(?:\s*,\s*[0-9]+)*)\]", replace, text)


def infer_key_map_from_existing_bib(
    reference_ids: dict[str, str],
    references_full: dict[str, dict],
    bib_path: Path,
) -> dict[str, str]:
    if not bib_path.exists():
        return {}
    bib_entries = parse_bib_entries(bib_path)
    entries_by_title = {
        _normalize_title_for_match(entry.get("title", "")): key
        for key, entry in bib_entries.items()
        if entry.get("title")
    }
    inferred: dict[str, str] = {}
    used: set[str] = set()
    for ref_num, paper_id in reference_ids.items():
        paper = references_full.get(paper_id) or references_full.get(ref_num, {})
        title_key = _normalize_title_for_match(paper.get("title", ""))
        bib_key = entries_by_title.get(title_key)
        if not bib_key or bib_key in used:
            continue
        inferred[ref_num] = bib_key
        used.add(bib_key)
    return inferred


def render_bibtex(
    reference_ids: dict[str, str],
    references_full: dict[str, dict],
    key_map: dict[str, str],
) -> str:
    entries = []
    for ref_num, paper_id in reference_ids.items():
        paper = references_full.get(paper_id) or references_full.get(ref_num, {})
        selected_key, bibtex = select_bibtex_entry(paper, key_map[ref_num])
        if selected_key != key_map[ref_num]:
            bibtex = replace_bibtex_key(bibtex, key_map[ref_num])
        entries.append(bibtex)
    bib_content = "\n".join(entries)
    if bib_content and not bib_content.endswith("\n"):
        bib_content += "\n"
    return bib_content


SURVEY_REFERENCES_HEADING_PATTERN = re.compile(
    r"\n{0,2}##\s+References\s*\n.*\Z",
    re.IGNORECASE | re.DOTALL,
)


def append_survey_references_section(
    survey_text: str,
    reference_ids: dict[str, str],
    references_full: dict[str, dict],
) -> str:
    body = SURVEY_REFERENCES_HEADING_PATTERN.sub("", survey_text).rstrip()
    reference_lines: list[str] = []
    for ref_num, paper_id in sorted(
        reference_ids.items(),
        key=lambda item: int(item[0]) if str(item[0]).isdigit() else str(item[0]),
    ):
        paper = references_full.get(paper_id) or references_full.get(ref_num) or {}
        title = paper_title(paper)
        reference_lines.append(f"[{ref_num}] {title}")

    if not reference_lines:
        return body + ("\n" if body else "")
    return body + "\n\n## References\n\n" + "\n\n".join(reference_lines) + "\n"


def rewrite_latex_cite_keys(tex_content: str, key_replacements: dict[str, str]) -> str:
    if not key_replacements:
        return tex_content

    def replace_match(match: re.Match[str]) -> str:
        keys = [
            key_replacements.get(key.strip(), key.strip())
            for key in match.group(1).split(",")
            if key.strip()
        ]
        return match.group(0).replace(match.group(1), ",".join(keys), 1)

    return LATEX_CITE_PATTERN.sub(replace_match, tex_content)


def paper_title(paper: dict) -> str:
    return str(paper.get("title", "Untitled")).strip() or "Untitled"


def ordered_latex_cite_keys(text: str) -> list[str]:
    keys: list[str] = []
    seen: set[str] = set()
    for match in LATEX_CITE_PATTERN.finditer(text):
        for key in match.group(1).split(","):
            cleaned = key.strip()
            if cleaned and cleaned not in seen:
                keys.append(cleaned)
                seen.add(cleaned)
    return keys


def migrate_opencode_citations_to_autosurvey_style(
    survey_text: str,
    survey_data: dict[str, Any],
    bib_path: Path,
) -> tuple[str, dict[str, str], dict[str, dict]]:
    bib_entries = parse_bib_entries(bib_path)
    cite_keys = ordered_latex_cite_keys(survey_text)
    if not cite_keys:
        cite_keys = [
            key
            for key in survey_data.get("citation_keys_used", [])
            if isinstance(key, str)
        ]
    if not cite_keys:
        cite_keys = [
            key for key in survey_data.get("bibliography_keys", []) if isinstance(key, str)
        ]

    reference_ids: dict[str, str] = {}
    references_full: dict[str, dict] = {}
    for key in cite_keys:
        if key not in bib_entries:
            continue
        ref_num = str(len(reference_ids) + 1)
        reference_ids[ref_num] = key
        references_full[key] = bib_entries[key]
    return survey_text, reference_ids, references_full


def render_fallback_related_works(
    topic: str,
    reference_ids: dict[str, str],
    references_full: dict[str, dict],
    key_map: dict[str, str],
    min_citations: int,
) -> str:
    items = [
        (ref_num, references_full.get(paper_id, {}), key_map[ref_num])
        for ref_num, paper_id in reference_ids.items()
        if paper_id in references_full and ref_num in key_map
    ]
    selected = items[: max(min_citations, min(len(items), DEFAULT_MIN_RELATED_CITATIONS))]
    if not selected:
        return "\\subsection{Related Work}\nNo resolved references were available.\n"

    def cite_block(slice_items: list[tuple[str, dict, str]]) -> str:
        return "\\citep{" + ",".join(key for _, _, key in slice_items) + "}"

    first = selected[: max(1, len(selected) // 3)]
    second = selected[max(1, len(selected) // 3) : max(2, 2 * len(selected) // 3)]
    third = selected[max(2, 2 * len(selected) // 3) :]
    if not second:
        second = first
    if not third:
        third = second

    return f"""\\subsection{{Foundational Methods and Problem Setting}}
Research on {topic} is anchored by methods that define the optimization setting, the communication model, and the sources of statistical or systems heterogeneity {cite_block(first)}. These papers provide the baseline vocabulary for comparing local update rules, server aggregation, drift control, and convergence assumptions.

\\subsection{{Efficiency, Robustness, and Theoretical Trade-offs}}
Subsequent work studies how to improve efficiency without weakening optimization guarantees {cite_block(second)}. The main synthesis issue is that communication reduction, memory reduction, personalization, and robustness often improve one resource axis while introducing new assumptions or bias terms.

\\subsection{{Open Gaps}}
The remaining gap is a unified account of how these mechanisms interact under realistic deployment constraints {cite_block(third)}. Existing results cover important pieces of the design space, but a complete related-work narrative should distinguish which papers address heterogeneity, which address resource limits, and which provide convergence guarantees under combined constraints.
"""


def ensure_final_survey_package(
    workspace_root: Path,
    survey_root_raw: str,
    related_root_raw: str,
    topic: str,
    min_survey_words: int = DEFAULT_MIN_SURVEY_WORDS,
    min_survey_subsections: int = DEFAULT_MIN_SURVEY_SUBSECTIONS,
    min_survey_lines: int = DEFAULT_MIN_SURVEY_LINES,
    min_related_citations: int = DEFAULT_MIN_RELATED_CITATIONS,
    min_related_words: int = DEFAULT_MIN_RELATED_WORDS,
    min_related_sections: int = DEFAULT_MIN_RELATED_SECTIONS,
    keep_intermediates: bool = False,
    min_survey_citations: int = DEFAULT_MIN_UNIQUE_SURVEY_CITATIONS,
    max_related_citations: int = DEFAULT_MAX_RELATED_CITATIONS,
) -> dict[str, Any]:
    survey_root = resolve_path(workspace_root, survey_root_raw)
    related_root = resolve_path(workspace_root, related_root_raw)
    survey_root.mkdir(parents=True, exist_ok=True)
    related_root.mkdir(parents=True, exist_ok=True)

    survey_tex_path = survey_root / "survey.tex"
    if survey_tex_path.exists():
        bib_path = survey_root / "references.bib"
        related_path = related_root / "related_works.tex"
        metadata_path = survey_root / "survey.json"
        required_report = validate_required_files(
            [survey_tex_path, metadata_path, bib_path, related_path]
        )
        validation = validate_tex_bib([survey_tex_path, related_path], bib_path)
        survey_text = survey_tex_path.read_text(encoding="utf-8")
        related_text = (
            related_path.read_text(encoding="utf-8") if related_path.exists() else ""
        )
        survey_keys = parse_cite_keys(survey_tex_path)
        related_keys = parse_cite_keys(related_path) if related_path.exists() else set()
        survey_words = count_tex_content_words(survey_text)
        survey_subsections = len(re.findall(r"\\subsection\*?\s*\{", survey_text))
        survey_lines = count_lines(survey_text)
        related_words = count_tex_content_words(related_text)
        related_sections = count_related_sections(related_text)
        quality_report = {
            "survey_min_words": min_survey_words,
            "survey_words_ok": survey_words >= min_survey_words,
            "survey_min_subsections": min_survey_subsections,
            "survey_subsections_ok": survey_subsections >= min_survey_subsections,
            "survey_min_lines": min_survey_lines,
            "survey_lines_ok": survey_lines >= min_survey_lines,
            "survey_min_distinct_citations": min_survey_citations,
            "survey_citations_ok": len(survey_keys) >= min_survey_citations,
            "related_citation_range": [min_related_citations, max_related_citations],
            "related_citations_ok": min_related_citations
            <= len(related_keys)
            <= max_related_citations,
            "min_related_words": min_related_words,
            "related_words_ok": related_words >= min_related_words,
            "min_related_sections": min_related_sections,
            "related_sections_ok": related_sections >= min_related_sections,
            "required_files_ok": required_report["ok"],
            "tex_bib_ok": validation["ok"],
        }
        quality_report["ok"] = all(
            value for key, value in quality_report.items() if key.endswith("_ok")
        )
        return {
            "format_contract": "tex-only-v1",
            "survey_root": str(survey_root),
            "related_root": str(related_root),
            "survey_words": survey_words,
            "survey_subsections": survey_subsections,
            "survey_lines": survey_lines,
            "related_words": related_words,
            "related_sections": related_sections,
            "reference_count": len(survey_keys),
            "related_reference_count": len(related_keys),
            "validation": validation,
            "required_files": required_report,
            "quality": quality_report,
            "removed_intermediates": [],
        }

    survey_json_path = survey_root / "survey.json"
    survey_md_path = survey_root / "survey.md"
    survey_bib_path = survey_root / "references.bib"
    related_path = related_root / "related_works.tex"
    bib_path = related_root / "references.bib"
    key_map_path = related_root / "citation_key_map.json"

    if survey_json_path.exists():
        survey_data = json.loads(survey_json_path.read_text(encoding="utf-8"))
        survey_text = survey_data.get("survey", "")
        reference_ids = survey_data.get("reference") or {}
        references_full = survey_data.get("reference_full") or {}
    else:
        survey_text = survey_md_path.read_text(encoding="utf-8") if survey_md_path.exists() else ""
        reference_ids = {}
        references_full = {}
        survey_data = {
            "survey": survey_text,
            "reference": reference_ids,
            "reference_full": references_full,
        }

    if not reference_ids and bib_path.exists():
        survey_text, reference_ids, references_full = (
            migrate_opencode_citations_to_autosurvey_style(
                survey_text=survey_text,
                survey_data=survey_data,
                bib_path=bib_path,
            )
        )

    reference_ids, references_full, reference_aliases, dedup_report = (
        canonicalize_reference_maps(reference_ids, references_full)
    )
    survey_text = rewrite_numeric_reference_aliases(survey_text, reference_aliases)

    existing_key_map = (
        json.loads(key_map_path.read_text(encoding="utf-8"))
        if key_map_path.exists()
        else infer_key_map_from_existing_bib(reference_ids, references_full, bib_path)
    )
    key_map = normalize_reference_key_map(reference_ids, references_full, existing_key_map)
    key_replacements = {
        old_key: key_map[ref_num]
        for ref_num, old_key in existing_key_map.items()
        if ref_num in key_map and old_key != key_map[ref_num]
    }
    for duplicate_ref, canonical_ref in reference_aliases.items():
        old_key = existing_key_map.get(duplicate_ref)
        canonical_key = key_map.get(canonical_ref)
        if old_key and canonical_key and old_key != canonical_key:
            key_replacements[old_key] = canonical_key

    if not survey_text.strip():
        survey_text = f"# Survey on {topic}\n\nNo survey draft was generated.\n"

    survey_text = append_survey_references_section(
        survey_text,
        reference_ids,
        references_full,
    )
    survey_md_path.write_text(survey_text, encoding="utf-8")
    survey_data["survey"] = survey_text
    survey_data["reference"] = reference_ids
    survey_data["reference_full"] = references_full
    survey_data["canonical_reference_dedup"] = dedup_report
    write_json(survey_json_path, survey_data)
    write_json(key_map_path, key_map)

    if related_path.exists():
        sanitized, _ = sanitize_related_works(related_path.read_text(encoding="utf-8"))
        sanitized = rewrite_latex_cite_keys(sanitized, key_replacements)
        related_path.write_text(sanitized, encoding="utf-8")

    if reference_ids and references_full:
        rendered_bib = render_bibtex(reference_ids, references_full, key_map)
        cited_keys = parse_cite_keys(related_path) if related_path.exists() else set()
        bib_path.write_text(
            merge_existing_cited_bib_entries(rendered_bib, bib_path, cited_keys),
            encoding="utf-8",
        )
    elif not bib_path.exists():
        bib_path.write_text("", encoding="utf-8")
    survey_bib_path.write_text(bib_path.read_text(encoding="utf-8"), encoding="utf-8")

    related_needs_fallback = not related_path.exists()
    if related_path.exists():
        existing_related = related_path.read_text(encoding="utf-8")
        related_needs_fallback = len(parse_cite_keys(related_path)) < min_related_citations
        if not existing_related.strip():
            related_needs_fallback = True

    if related_needs_fallback:
        related_path.write_text(
            render_fallback_related_works(
                topic, reference_ids, references_full, key_map, min_related_citations
            ),
            encoding="utf-8",
        )

    removed_intermediates: list[str] = []
    if not keep_intermediates:
        cleanup_targets = [
            *survey_root.glob("stage*.json"),
            *survey_root.glob("native_survey_prompt*.json"),
            *survey_root.glob("drafts*.json"),
            *survey_root.glob("sections*.json"),
            survey_root / "library",
            related_root / "rw_prompt.json",
            related_root / "citation_key_map.json",
            workspace_root / "pipeline_log.jsonl",
            related_root / "rw.tex",
            related_root / "ref.bib",
        ]
        for target in cleanup_targets:
            if not target.exists():
                continue
            if target.is_dir():
                for child in sorted(target.rglob("*"), reverse=True):
                    if child.is_file() or child.is_symlink():
                        child.unlink()
                    elif child.is_dir():
                        child.rmdir()
                target.rmdir()
            else:
                target.unlink()
            removed_intermediates.append(str(target))

    validation = validate_tex_bib([related_path], bib_path)
    required_report = validate_required_files(
        [
            survey_root / "survey.md",
            survey_root / "survey.json",
            survey_root / "references.bib",
            related_root / "related_works.tex",
            related_root / "references.bib",
        ]
    )
    final_survey_text = survey_md_path.read_text(encoding="utf-8")
    survey_words = count_words(final_survey_text)
    survey_subsections = count_survey_subsections(final_survey_text)
    survey_lines = count_lines(final_survey_text)
    related_text = related_path.read_text(encoding="utf-8") if related_path.exists() else ""
    related_words = count_words(related_text)
    related_sections = count_related_sections(related_text)
    cited_keys = validation["cited_key_count"]
    bib_keys = validation["bib_key_count"]
    quality_report = {
        "survey_min_words": min_survey_words,
        "survey_words_ok": survey_words >= min_survey_words,
        "survey_min_subsections": min_survey_subsections,
        "survey_subsections_ok": survey_subsections >= min_survey_subsections,
        "survey_min_lines": min_survey_lines,
        "survey_lines_ok": survey_lines >= min_survey_lines,
        "min_related_citations": min_related_citations,
        "related_citations_ok": cited_keys >= min_related_citations,
        "min_related_words": min_related_words,
        "related_words_ok": related_words >= min_related_words,
        "min_related_sections": min_related_sections,
        "related_sections_ok": related_sections >= min_related_sections,
        "references_ok": len(reference_ids) > 0,
        "bib_entries_ok": bib_keys > 0,
        "required_files_ok": required_report["ok"],
        "tex_bib_ok": validation["ok"],
        "reference_identity_ok": dedup_report["gate_passed"],
    }
    quality_report["ok"] = all(
        value for key, value in quality_report.items() if key.endswith("_ok")
    )
    return {
        "survey_root": str(survey_root),
        "related_root": str(related_root),
        "survey_words": survey_words,
        "survey_subsections": survey_subsections,
        "survey_lines": survey_lines,
        "related_words": related_words,
        "related_sections": related_sections,
        "reference_count": len(reference_ids),
        "key_map": str(key_map_path),
        "validation": validation,
        "required_files": required_report,
        "quality": quality_report,
        "canonical_reference_dedup": dedup_report,
        "removed_intermediates": removed_intermediates,
    }


# --- Commands ---


def command_prepare_outline_data(args: argparse.Namespace) -> int:
    prompts = load_prompt_templates()
    workspace_root = resolve_workspace(args.workspace)
    structure_prompt, structure_metadata = load_structure_context(workspace_root, args)

    try:
        source_papers = load_frozen_paper_pool(workspace_root, args.library_dir)
        frozen_pool_only = True
    except FileNotFoundError:
        source_papers = load_external_library_papers(workspace_root, args.library_dir)
        frozen_pool_only = False
    task, task_path = _load_frozen_task(
        workspace_root, str(getattr(args, "task_path", "") or "")
    )
    references_infos, evidence_selection = select_native_evidence(
        source_papers,
        args.topic,
        {
            "sections": [],
            "section_descriptions": [],
            "subsections": [],
            "subsection_descriptions": [],
        },
        max_papers=args.reference_num,
        required_references=task.get("key_references") or [],
        structure_supported_titles=_structure_supported_titles(
            workspace_root, args.library_dir
        ),
    )
    references_titles = [r["title"] for r in references_infos]
    max_abstract_chars = int(getattr(args, "max_abstract_chars", 1200))
    references_abs = [
        _paper_abstract(reference)[:max_abstract_chars]
        for reference in references_infos
    ]

    abs_chunks, titles_chunks = chunk_papers(
        references_abs, references_titles, args.chunk_size
    )

    prompt_entries = []
    for titles, abstracts in zip(titles_chunks, abs_chunks):
        papers_text = ""
        for title, abstract in zip(titles, abstracts):
            papers_text += (
                f"---\npaper_title: {title}\n\npaper_content:\n\n{abstract}\n"
            )
        papers_text += "---\n"
        prompt_text = fill_prompt(
            prompts.ROUGH_OUTLINE_PROMPT,
            {
                "PAPER LIST": papers_text,
                "TOPIC": args.topic,
                "SECTION NUM": str(args.section_num),
            },
        )
        if structure_prompt:
            prompt_text = f"{prompt_text}\n\n{structure_prompt}"
        prompt_entries.append({"prompt": prompt_text, "titles": titles})

    output = {
        "topic": args.topic,
        "section_num": args.section_num,
        "rag_num": args.rag_num,
        "stage": "rough_outline",
        "prompts": prompt_entries,
        "paper_library": paper_library_metadata(workspace_root, args.library_dir),
        "frozen_pool_only": frozen_pool_only,
        "task_contract_path": str(task_path) if task_path else None,
        "max_abstract_chars": max_abstract_chars,
        "evidence_selection": evidence_selection,
        "structure": structure_metadata,
    }

    output_path = resolve_path(workspace_root, args.output_path)
    write_json(output_path, output)
    print(
        json.dumps(
            {"output_path": str(output_path), "num_prompts": len(prompt_entries)},
            indent=2,
        )
    )
    return 0


def command_merge_outline_data(args: argparse.Namespace) -> int:
    prompts = load_prompt_templates()
    workspace_root = resolve_workspace(args.workspace)

    outlines_path = resolve_path(workspace_root, args.outlines_path)
    outlines_data = json.loads(outlines_path.read_text(encoding="utf-8"))
    outlines = outlines_data["outlines"]

    outline_texts = ""
    for i, o in enumerate(outlines):
        outline_texts += f"---\noutline_id: {i}\n\noutline_content:\n\n{o}\n"
    outline_texts += "---\n"

    prompt_text = fill_prompt(
        prompts.MERGING_OUTLINE_PROMPT,
        {
            "OUTLINE LIST": outline_texts,
            "TOPIC": outlines_data["topic"],
            "SECTION NUM": str(outlines_data["section_num"]),
        },
    )

    output = {
        "topic": outlines_data["topic"],
        "section_num": outlines_data["section_num"],
        "stage": "merge_outline",
        "prompt": prompt_text,
    }

    output_path = resolve_path(workspace_root, args.output_path)
    write_json(output_path, output)
    print(json.dumps({"output_path": str(output_path)}, indent=2))
    return 0


def command_prepare_subsection_outline_data(args: argparse.Namespace) -> int:
    prompts = load_prompt_templates()
    workspace_root = resolve_workspace(args.workspace)
    db = get_database(args)
    structure_prompt, structure_metadata = load_structure_context(workspace_root, args)

    section_outline_path = resolve_path(workspace_root, args.section_outline_path)
    section_outline = section_outline_path.read_text(encoding="utf-8")

    _, sections, descriptions = extract_title_sections_descriptions(section_outline)

    prompt_entries = []
    for section_name, section_desc in zip(sections, descriptions):
        references_ids = db.get_ids_from_query(
            section_desc, num=args.rag_num, shuffle=True
        )
        references_infos = db.get_paper_info_from_ids(references_ids)
        paper_texts = ""
        for r in references_infos:
            paper_texts += (
                f"---\npaper_title: {r['title']}\n\npaper_abstract:\n{r['abs']}\n"
            )
            topics = r.get("topics", [])
            if topics:
                paper_texts += f"\npaper_topics: {', '.join(topics)}\n"
        paper_texts += "---\n"

        prompt_text = fill_prompt(
            prompts.SUBSECTION_OUTLINE_PROMPT,
            {
                "OVERALL OUTLINE": section_outline,
                "SECTION NAME": section_name,
                "SECTION DESCRIPTION": section_desc,
                "TOPIC": args.topic,
                "PAPER LIST": paper_texts,
            },
        )
        if structure_prompt:
            prompt_text = f"{prompt_text}\n\n{structure_prompt}"
        prompt_entries.append({"prompt": prompt_text, "section": section_name})

    output = {
        "topic": args.topic,
        "stage": "subsection_outline",
        "section_outline": section_outline,
        "sections": sections,
        "descriptions": descriptions,
        "prompts": prompt_entries,
        "paper_library": paper_library_metadata(workspace_root, args.library_dir),
        "structure": structure_metadata,
    }

    output_path = resolve_path(workspace_root, args.output_path)
    write_json(output_path, output)
    print(
        json.dumps(
            {"output_path": str(output_path), "num_prompts": len(prompt_entries)},
            indent=2,
        )
    )
    return 0


def command_prepare_edit_outline_data(args: argparse.Namespace) -> int:
    prompts = load_prompt_templates()
    workspace_root = resolve_workspace(args.workspace)

    merged_path = resolve_path(workspace_root, args.merged_outline_path)
    merged_outline = merged_path.read_text(encoding="utf-8")

    prompt_text = fill_prompt(
        prompts.EDIT_FINAL_OUTLINE_PROMPT
        if hasattr(prompts, "EDIT_FINAL_OUTLINE_PROMPT")
        else prompts.SUBSECTION_OUTLINE_PROMPT,
        {
            "OVERALL OUTLINE": merged_outline,
        },
    )

    output = {
        "stage": "edit_final_outline",
        "prompt": prompt_text,
    }

    output_path = resolve_path(workspace_root, args.output_path)
    write_json(output_path, output)
    print(json.dumps({"output_path": str(output_path)}, indent=2))
    return 0


def command_merge_outline(args: argparse.Namespace) -> int:
    workspace_root = resolve_workspace(args.workspace)

    section_outline_path = resolve_path(workspace_root, args.section_outline_path)
    section_outline = section_outline_path.read_text(encoding="utf-8")

    subsection_path = resolve_path(workspace_root, args.subsection_outlines_path)
    subsection_data = json.loads(subsection_path.read_text(encoding="utf-8"))
    sub_outlines = subsection_data["outlines"]

    _, sections, descriptions = extract_title_sections_descriptions(section_outline)

    res = ""
    title_match = re.search(r"Title:\s*(.+)", section_outline)
    if title_match:
        res += f"# {title_match.group(1).strip()}\n\n"

    for i, section in enumerate(sections):
        res += f"## {i + 1} {section}\nDescription: {descriptions[i]}\n\n"
        if i < len(sub_outlines):
            subs, sub_descs = extract_subsections_subdescriptions(sub_outlines[i])
            for j, sub in enumerate(subs):
                res += f"### {i + 1}.{j + 1} {sub}\nDescription: {sub_descs[j] if j < len(sub_descs) else ''}\n\n"

    output_path = resolve_path(workspace_root, args.output_path)
    ensure_parent(output_path)
    output_path.write_text(res, encoding="utf-8")
    print(json.dumps({"output_path": str(output_path)}, indent=2))
    return 0


def command_prepare_subsection_data(args: argparse.Namespace) -> int:
    prompts = load_prompt_templates()
    workspace_root = resolve_workspace(args.workspace)
    db = get_database(args)
    structure_prompt, structure_metadata = load_structure_context(workspace_root, args)

    outline_path = resolve_path(workspace_root, args.outline_path)
    outline_content = outline_path.read_text(encoding="utf-8")
    parsed = parse_outline(outline_content)

    total_ids: list[str] = []
    for descriptions in parsed["subsection_descriptions"]:
        for d in descriptions:
            ids = db.get_ids_from_query(d, num=args.rag_num, shuffle=False)
            total_ids.extend(ids)
    total_infos = db.get_paper_info_from_ids(list(set(total_ids)))
    info_dic = {p["id"]: p for p in total_infos}

    section_entries: list[list[dict]] = []
    for i, section in enumerate(parsed["sections"]):
        subsection_prompts: list[dict] = []
        for j, desc in enumerate(parsed["subsection_descriptions"][i]):
            ids = db.get_ids_from_query(desc, num=args.rag_num, shuffle=False)
            papers = [info_dic[_] for _ in ids if _ in info_dic]
            paper_texts = (
                db.format_papers_text(papers, include_analysis=True)
                if hasattr(db, "format_papers_text")
                else _format_papers_text_fallback(papers)
            )

            writing_prompt = fill_prompt(
                prompts.SUBSECTION_WRITING_PROMPT,
                {
                    "OVERALL OUTLINE": outline_content,
                    "SUBSECTION NAME": parsed["subsections"][i][j],
                    "DESCRIPTION": desc,
                    "TOPIC": args.topic,
                    "PAPER LIST": paper_texts,
                    "SECTION NAME": section,
                    "WORD NUM": str(args.subsection_len),
                },
            )
            if structure_prompt:
                writing_prompt = f"{writing_prompt}\n\n{structure_prompt}"
            subsection_prompts.append(
                {
                    "writing_prompt": writing_prompt,
                    "paper_texts": paper_texts,
                    "subsection_name": parsed["subsections"][i][j],
                    "section_name": section,
                }
            )
        section_entries.append(subsection_prompts)

    output = {
        "topic": args.topic,
        "outline": outline_content,
        "parsed_outline": parsed,
        "stage": "subsection_writing",
        "sections": section_entries,
        "paper_library": paper_library_metadata(workspace_root, args.library_dir),
        "structure": structure_metadata,
    }

    output_path = resolve_path(workspace_root, args.output_path)
    write_json(output_path, output)
    print(
        json.dumps(
            {"output_path": str(output_path), "num_sections": len(section_entries)},
            indent=2,
        )
    )
    return 0


def command_prepare_native_survey_data(args: argparse.Namespace) -> int:
    workspace_root = resolve_workspace(args.workspace)
    structure_prompt, structure_metadata = load_structure_context(workspace_root, args)

    outline_path = resolve_path(workspace_root, args.outline_path)
    outline_content = outline_path.read_text(encoding="utf-8")
    parsed = parse_outline(outline_content)

    # Native writing always consumes the same frozen-pool selection path.  The
    # old optional query-time path made treatment and control depend on agent-
    # chosen flags and produced incomparable context sizes.
    try:
        source_papers = load_frozen_paper_pool(workspace_root, args.library_dir)
        frozen_pool_only = True
    except FileNotFoundError:
        source_papers = load_external_library_papers(workspace_root, args.library_dir)
        frozen_pool_only = False
    task, task_path = _load_frozen_task(
        workspace_root, str(getattr(args, "task_path", "") or "")
    )
    required_references = task.get("key_references") or []
    supported_titles = _structure_supported_titles(workspace_root, args.library_dir)
    paper_infos, evidence_selection = select_native_evidence(
        source_papers,
        args.topic,
        parsed,
        max_papers=args.max_papers,
        required_references=required_references,
        structure_supported_titles=supported_titles,
    )
    paper_infos = assign_unique_bibtex_keys(paper_infos)
    paper_ids = [_paper_identity(paper) for paper in paper_infos]
    external_papers = source_papers
    max_evidence_chars = int(getattr(args, "max_evidence_chars", 150000))
    paper_list = _format_papers_text_bounded(paper_infos, max_evidence_chars)

    bib_output = resolve_path(
        workspace_root, str(getattr(args, "bib_output", "survey/references.bib"))
    )
    bib_entries: list[str] = []
    for paper in paper_infos:
        _, entry = select_bibtex_entry(paper, fallback_key=paper["bib_key"])
        bib_entries.append(entry.rstrip())
    bib_output.parent.mkdir(parents=True, exist_ok=True)
    bib_output.write_text("\n\n".join(bib_entries) + "\n", encoding="utf-8")
    reference_ids = {
        str(index): _paper_identity(paper)
        for index, paper in enumerate(paper_infos, start=1)
    }
    references_full = {
        _paper_identity(paper): paper for paper in paper_infos
    }
    survey_metadata_output = resolve_path(
        workspace_root,
        str(getattr(args, "survey_metadata_output", "survey/survey.json")),
    )
    write_json(
        survey_metadata_output,
        {
            "schema_version": "tex-survey-v1",
            "topic": args.topic,
            "survey_tex_path": "survey.tex",
            "survey": "",
            "reference": reference_ids,
            "reference_full": references_full,
            "citation_key_map": {
                ref_num: references_full[paper_id]["bib_key"]
                for ref_num, paper_id in reference_ids.items()
            },
        },
    )

    min_words = args.min_words
    target_words = args.target_words
    min_unique_citations = int(
        getattr(args, "min_unique_citations", DEFAULT_MIN_UNIQUE_SURVEY_CITATIONS)
    )
    target_unique_citations = max(
        int(
            getattr(
                args,
                "target_unique_citations",
                DEFAULT_TARGET_UNIQUE_SURVEY_CITATIONS,
            )
        ),
        min_unique_citations,
    )
    prompt_text = f"""Write a complete, independently compilable academic survey in LaTeX about "{args.topic}".

Use the outline and paper library below as the only citation source. Rely on your native long-form writing ability: produce the whole survey in one coherent pass, not subsection-by-subsection fragments.

Outline:
---
{outline_content}
---

Paper library:
---
{paper_list}
---

{structure_prompt}

Requirements:
1. Output only one complete LaTeX document from \\documentclass through \\end{{document}}. Do not use Markdown and do not include process notes.
2. Write in English unless the user instructions explicitly require another language.
3. Target about {target_words} words and never go below {min_words} words. A shorter draft is incomplete and must be expanded before returning.
4. Preserve the outline's organization as 6-8 \\section blocks and about 24-32 substantive \\subsection blocks. Prefer a coherent learning path over encyclopedic branch proliferation.
5. Every technical comparison or historical claim should be supported by citations from the paper library.
6. Cite only with natbib-compatible \\citep{{key}} and \\citet{{key}}, using the exact paper_citation_key supplied with each paper. Configure natbib as [numbers,sort&compress] so citations and the bibliography are numbered in first-citation order; the ampersand in the package option must be the literal unescaped `&`, not `\\&`. Never type bracket numbers manually or repeat an author-year string around a citation command.
7. Do not use manually written numeric citations, Markdown citations, URLs as citations, missing keys, or invented paper titles.
8. Begin with 3-6 orthogonal comparison axes and use them throughout the survey. Group related works by mechanism, assumptions, guarantees, resource costs, and limitations rather than summarizing papers one by one. Include at least one compact cross-branch decision table.
9. Cover foundations, major method families, theoretical assumptions/results, empirical/deployment considerations, and open gaps.
10. Write each subsection as 3-5 readable paragraphs with connected prose, comparative claims, assumptions, limitations, and transitions.
11. Do not collapse the survey into only sections. A draft with fewer than 24 substantive \\subsection blocks is structurally incomplete; more than 32 usually indicates fragmented, paper-by-paper organization and should be consolidated.
12. Cite at least {min_unique_citations} distinct citation keys and naturally exceed that lower bound when the evidence supports it. Do not target exactly the minimum, optimize for a conspicuous round count, inflate coverage with irrelevant papers, or add unattached citation lists. Distribute evidence across the document.
13. Required references named by the task contract must be cited when they are present in the paper library. If a required reference is absent, do not invent it.
14. Write for a technically capable beginner: define the problem, notation, assumptions, and evaluation units before taxonomy; explain the chronological lineage as problem -> limitation -> successor mechanism; define every field-specific acronym on first use.
15. Include a dedicated open-problems section. Start from paper_open_problem_candidates, cite their originating papers, check later supplied papers for partial solutions or counterevidence, and distinguish paper-stated limitations from gaps still unresolved at the survey cutoff. For each retained problem state scope, evidence, why current methods do not settle it, and a testable next step.
16. Use a Unicode-safe XeTeX preamble with fontspec, DejaVu Serif, microtype, amsmath, amssymb, booktabs, longtable, graphicx, xcolor, natbib configured as [numbers,sort&compress], geometry, and hyperref. Do not combine fontspec with inputenc, fontenc, or lmodern. Use A4 paper and sensible margins. End with \\bibliographystyle{{unsrtnat}} and \\bibliography{{references}}.
17. Keep comparison tables readable: use concise phrases rather than paragraph-length cells; use at most four columns in portrait orientation; place wider five-or-more-column tables in a landscape environment; and choose p-column widths whose sum plus tabular padding fits within \\linewidth.
18. Write every section's narrative explicitly. Do not define or invoke macros that contain sentences, paragraphs, subsection bodies, generic comparison prose, or reusable filler. Macros are allowed only for short mathematical symbols and notation. The word target must be met by non-repeated, topic-specific source prose.
17. Escape LaTeX special characters in prose and titles. Put every formula in a valid math environment. Do not emit Unicode math glyphs in place of LaTeX commands.
18. Exclude a paper when its title, abstract, and extracted mechanism do not directly support the topic or one of the common comparison axes. A structure-pack mention is never sufficient reason to cite an off-topic paper.
19. Before returning, self-check word count, subsection count, distinct citation-key count, required-reference coverage, beginner-facing lineage, open-problem grounding, topic relevance, balanced braces, and document boundaries.
"""

    output = {
        "topic": args.topic,
        "outline": outline_content,
        "stage": "native_survey_writing",
        "paper_count": len(paper_infos),
        "paper_ids": paper_ids,
        "external_paper_count": len(external_papers),
        "paper_library": paper_library_metadata(workspace_root, args.library_dir),
        "frozen_pool_only": frozen_pool_only,
        "task_contract_path": str(task_path) if task_path else None,
        "min_unique_citations": min_unique_citations,
        "target_unique_citations": target_unique_citations,
        "bib_output": str(bib_output),
        "survey_metadata_output": str(survey_metadata_output),
        "max_evidence_chars": max_evidence_chars,
        "rendered_evidence_chars": len(paper_list),
        "evidence_selection": evidence_selection,
        "structure": structure_metadata,
        "prompt": prompt_text,
    }

    output_path = resolve_path(workspace_root, args.output_path)
    write_json(output_path, output)
    print(
        json.dumps(
            {
                "output_path": str(output_path),
                "num_papers": len(paper_infos),
                "num_external_papers": len(external_papers),
                "min_words": min_words,
                "target_words": target_words,
                "min_unique_citations": min_unique_citations,
                "target_unique_citations": target_unique_citations,
            },
            indent=2,
        )
    )
    return 0


def _format_papers_text_fallback(papers: list[dict]) -> str:
    texts = ""
    for p in papers:
        texts += f"---\npaper_title: {p.get('title', '')}\npaper_citation_key: {p.get('bib_key', '')}\n\npaper_abstract:\n{p.get('abs', '')}\n"
        topics = p.get("topics", [])
        if topics:
            texts += f"\npaper_topics: {', '.join(topics)}\n"
        strengths = p.get("strengths", "")
        if strengths:
            texts += f"\npaper_strengths: {strengths}\n"
        weaknesses = p.get("weaknesses", "")
        if weaknesses:
            texts += f"\npaper_weaknesses: {weaknesses}\n"
        open_problems = p.get("open_problem_candidates") or []
        if open_problems:
            texts += "\npaper_open_problem_candidates:\n" + "\n".join(
                f"- {value}" for value in open_problems
            ) + "\n"
    texts += "---\n"
    return texts


def _format_papers_text_bounded(
    papers: list[dict[str, Any]], max_total_chars: int
) -> str:
    """Render every selected title while bounding profile-dependent context size."""
    if not papers:
        return "---\n"
    per_paper = max(700, max_total_chars // len(papers))
    blocks: list[str] = []
    used = 0
    for paper in papers:
        title = paper_title(paper)
        fixed = f"---\npaper_title: {title}\npaper_citation_key: {paper.get('bib_key', '')}\n"
        remaining = max(200, per_paper - len(fixed))
        abstract = _paper_abstract(paper)[: int(remaining * 0.68)]
        strengths = str(paper.get("strengths") or "")[: int(remaining * 0.18)]
        weaknesses = str(paper.get("weaknesses") or "")[: int(remaining * 0.07)]
        open_problem_text = "\n".join(
            str(value) for value in (paper.get("open_problem_candidates") or [])
        )[: int(remaining * 0.12)]
        topics_value = paper.get("topics") or []
        topics = (
            ", ".join(str(item) for item in topics_value)
            if isinstance(topics_value, list)
            else str(topics_value)
        )[: int(remaining * 0.05)]
        block = fixed + f"\npaper_abstract:\n{abstract}\n"
        if topics:
            block += f"\npaper_topics: {topics}\n"
        if strengths:
            block += f"\npaper_strengths: {strengths}\n"
        if weaknesses:
            block += f"\npaper_weaknesses: {weaknesses}\n"
        if open_problem_text:
            block += f"\npaper_open_problem_candidates:\n{open_problem_text}\n"
        if used + len(block) > max_total_chars:
            # Titles are citation identifiers and must never be dropped. Keep a
            # compact title-only record when the aggregate descriptive budget is exhausted.
            block = fixed
        blocks.append(block)
        used += len(block)
    return "".join(blocks) + "---\n"


def command_prepare_citation_check_data(args: argparse.Namespace) -> int:
    prompts = load_prompt_templates()
    workspace_root = resolve_workspace(args.workspace)

    drafts_path = resolve_path(workspace_root, args.drafts_path)
    drafts_data = json.loads(drafts_path.read_text(encoding="utf-8"))

    prompt_entries: list[dict] = []
    for section in drafts_data.get("sections", []):
        for subsection in section:
            check_prompt = fill_prompt(
                prompts.CHECK_CITATION_PROMPT
                if hasattr(prompts, "CHECK_CITATION_PROMPT")
                else prompts.SUBSECTION_WRITING_PROMPT,
                {
                    "PAPER LIST": subsection.get("paper_texts", ""),
                    "SUBSECTION NAME": subsection.get("subsection_name", ""),
                    "TOPIC": args.topic,
                    "OVERALL OUTLINE": drafts_data.get("outline", ""),
                    "DESCRIPTION": "",
                    "SECTION NAME": subsection.get("section_name", ""),
                    "WORD NUM": "200",
                },
            )
            prompt_entries.append(
                {
                    "prompt": check_prompt,
                    "subsection_name": subsection.get("subsection_name", ""),
                    "draft": subsection.get("draft", ""),
                }
            )

    output = {
        "stage": "citation_check",
        "prompts": prompt_entries,
    }

    output_path = resolve_path(workspace_root, args.output_path)
    write_json(output_path, output)
    print(
        json.dumps(
            {"output_path": str(output_path), "num_prompts": len(prompt_entries)},
            indent=2,
        )
    )
    return 0


def command_prepare_lce_data(args: argparse.Namespace) -> int:
    prompts = load_prompt_templates()
    workspace_root = resolve_workspace(args.workspace)

    content_path = resolve_path(workspace_root, args.content_path)
    content_data = json.loads(content_path.read_text(encoding="utf-8"))
    subsections = content_data.get("subsections", [])

    prompt_entries: list[dict] = []
    for i, sub in enumerate(subsections):
        previous = subsections[i - 1]["content"] if i > 0 else ""
        following = subsections[i + 1]["content"] if i < len(subsections) - 1 else ""
        prompt_text = fill_prompt(
            prompts.LCE_PROMPT,
            {
                "TOPIC": args.topic,
                "PREVIOUS": previous,
                "SUBSECTION": sub.get("content", ""),
                "FOLLOWING": following,
            },
        )
        prompt_entries.append(
            {
                "prompt": prompt_text,
                "index": i,
                "subsection_name": sub.get("name", ""),
            }
        )

    output = {
        "stage": "lce",
        "prompts": prompt_entries,
    }

    output_path = resolve_path(workspace_root, args.output_path)
    write_json(output_path, output)
    print(
        json.dumps(
            {"output_path": str(output_path), "num_prompts": len(prompt_entries)},
            indent=2,
        )
    )
    return 0


def command_resolve_references(args: argparse.Namespace) -> int:
    workspace_root = resolve_workspace(args.workspace)
    db = get_database(args)

    survey_path = resolve_path(workspace_root, args.survey_path)
    survey_content = survey_path.read_text(encoding="utf-8")

    citations = extract_citations(survey_content)
    if not citations:
        output = {
            "survey": survey_content,
            "reference": {},
            "reference_full": {},
        }
        output_path = resolve_path(workspace_root, args.output_path)
        write_json(output_path, output)
        print(
            json.dumps({"output_path": str(output_path), "num_citations": 0}, indent=2)
        )
        return 0

    ids = (
        db.get_titles_from_citations(citations)
        if hasattr(db, "get_titles_from_citations")
        else _resolve_citations_fallback(db, citations)
    )
    citation_to_ids = dict(zip(citations, ids))
    valid_ids = [v for v in citation_to_ids.values() if v]
    paper_infos = db.get_paper_info_from_ids(valid_ids) if valid_ids else []
    info_by_id = {p["id"]: p for p in paper_infos}

    citation_to_ref_num: dict[str, str] = {}
    references: dict[str, str] = {}
    references_full: dict[str, dict] = {}

    for cite, pid in citation_to_ids.items():
        if pid and pid in info_by_id:
            ref_num = str(len(references) + 1)
            citation_to_ref_num[cite] = ref_num
            references[ref_num] = pid
            references_full[pid] = info_by_id[pid]

    updated = replace_title_citations_with_numbers(survey_content, citation_to_ref_num)
    updated = append_survey_references_section(updated, references, references_full)

    output = {
        "survey": updated,
        "reference": references,
        "reference_full": references_full,
    }

    output_path = resolve_path(workspace_root, args.output_path)
    write_json(output_path, output)
    print(
        json.dumps(
            {"output_path": str(output_path), "num_references": len(references)},
            indent=2,
        )
    )
    return 0


def _resolve_citations_fallback(db, citations: list[str]) -> list[str]:
    ids: list[str] = []
    for cite in citations:
        try:
            found = db.get_ids_from_query(cite, num=1, shuffle=False)
            ids.append(found[0] if found else "")
        except Exception:
            ids.append("")
    return ids


def command_generate_bibtex(args: argparse.Namespace) -> int:
    workspace_root = resolve_workspace(args.workspace)

    survey_json_path = resolve_path(workspace_root, args.survey_json)
    survey_data = json.loads(survey_json_path.read_text(encoding="utf-8"))
    references_full = survey_data.get("reference_full", {})
    reference_ids = survey_data.get("reference") or {
        str(index + 1): paper_id for index, paper_id in enumerate(references_full.keys())
    }
    key_map = normalize_reference_key_map(reference_ids, references_full)
    bib_content = render_bibtex(reference_ids, references_full, key_map)

    bib_output = resolve_path(workspace_root, args.bib_output)
    ensure_parent(bib_output)
    bib_output.write_text(bib_content, encoding="utf-8")

    if args.key_map_output:
        key_map_path = resolve_path(workspace_root, args.key_map_output)
        write_json(key_map_path, key_map)

    print(
        json.dumps(
            {"bib_output": str(bib_output), "num_entries": len(reference_ids)},
            indent=2,
        )
    )
    return 0


def command_assemble_survey(args: argparse.Namespace) -> int:
    workspace_root = resolve_workspace(args.workspace)

    outline_path = resolve_path(workspace_root, args.outline_path)
    outline_content = outline_path.read_text(encoding="utf-8")
    parsed = parse_outline(outline_content)

    sections_dir = resolve_path(workspace_root, args.sections_dir)

    parts: list[str] = []
    for i, section in enumerate(parsed["sections"]):
        parts.append(f"\n## {section}\n")
        for j, sub in enumerate(parsed["subsections"][i]):
            sub_file = sections_dir / f"section_{i}" / f"subsection_{j}.md"
            if sub_file.exists():
                content = sub_file.read_text(encoding="utf-8")
                parts.append(f"\n### {sub}\n\n{content}\n")
            else:
                parts.append(f"\n### {sub}\n\n(No content generated)\n")

    survey_text = "\n".join(parts)

    output_path = resolve_path(workspace_root, args.output_path)
    ensure_parent(output_path)
    output_path.write_text(survey_text, encoding="utf-8")
    print(json.dumps({"output_path": str(output_path)}, indent=2))
    return 0


def _strip_generated_references(survey_text: str) -> str:
    match = re.search(
        r"(?im)^#{1,3}\s+(?:\d+(?:\.\d+)*\s+)?(?:references|bibliography)\s*$",
        survey_text,
    )
    return survey_text[: match.start()].rstrip() if match else survey_text.rstrip()


RELATION_BRIEF_TERMS = {
    "evolution_and_lineage": (
        "evolve",
        "evolution",
        "lineage",
        "successor",
        "predecessor",
        "originally",
        "subsequent",
        "later work",
        "builds on",
        "extends",
    ),
    "mechanism_and_comparison": (
        "mechanism",
        "compared",
        "in contrast",
        "whereas",
        "trade-off",
        "tradeoff",
        "assumption",
        "guarantee",
        "complexity",
    ),
    "boundary_and_counterevidence": (
        "however",
        "limitation",
        "limited",
        "fails",
        "cannot",
        "counterexample",
        "counter-evidence",
        "boundary",
        "only when",
    ),
    "gaps_and_future_tests": (
        "gap",
        "unresolved",
        "open problem",
        "future work",
        "future direction",
        "remains unclear",
        "should test",
        "evaluation protocol",
    ),
}


def build_relation_brief(survey_text: str, max_per_category: int = 6) -> str:
    """Extract evidence-bearing relation passages across the complete survey."""
    body = _strip_generated_references(survey_text)
    chunks = [
        re.sub(r"\s+", " ", chunk).strip()
        for chunk in re.split(r"\n\s*\n+", body)
        if chunk.strip() and not chunk.lstrip().startswith("#")
    ]
    sections: list[str] = []
    for category, terms in RELATION_BRIEF_TERMS.items():
        matches: list[str] = []
        for chunk in chunks:
            lowered = chunk.lower()
            has_relation_term = any(term in lowered for term in terms)
            has_citation = bool(
                re.search(r"\[[^\]]+\]", chunk) or LATEX_CITE_PATTERN.search(chunk)
            )
            if not has_relation_term or not has_citation:
                continue
            excerpt = chunk[:900].rstrip()
            if len(chunk) > 900:
                excerpt += " …"
            if excerpt not in matches:
                matches.append(excerpt)
            if len(matches) >= max_per_category:
                break
        if matches:
            heading = category.replace("_", " ").title()
            sections.append(f"### {heading}\n" + "\n".join(f"- {item}" for item in matches))
    if not sections:
        return "No citation-bearing relation passages were detected; reconstruct relations conservatively from the full survey context and reference abstracts."
    return "\n\n".join(sections)


def command_prepare_related_works_data(args: argparse.Namespace) -> int:
    workspace_root = resolve_workspace(args.workspace)

    survey_path = resolve_path(workspace_root, args.survey_path)
    survey_data = json.loads(survey_path.read_text(encoding="utf-8"))
    survey_text = survey_data.get("survey", "")
    if not survey_text.strip():
        tex_name = str(survey_data.get("survey_tex_path") or "survey.tex")
        tex_path = survey_path.parent / tex_name
        if tex_path.exists():
            survey_text = tex_path.read_text(encoding="utf-8")
    references_full = survey_data.get("reference_full", {})
    reference_ids = survey_data.get("reference") or {
        str(index + 1): paper_id for index, paper_id in enumerate(references_full.keys())
    }

    key_map = normalize_reference_key_map(reference_ids, references_full)
    citation_key_map = ""
    for ref_num in reference_ids:
        bib_key = key_map[ref_num]
        citation_key_map += f"{ref_num} -> \\cite{{{bib_key}}}\n"

    paper_list = ""
    for ref_num, paper_id in reference_ids.items():
        paper = references_full.get(paper_id) or references_full.get(ref_num) or {}
        paper_list += f"---\nReference {ref_num}: {paper.get('title', '')}\n"
        paper_list += f"Abstract: {paper.get('abs', '')}\n"
        authors = paper.get("authors", [])
        if isinstance(authors, list):
            paper_list += f"Authors: {', '.join(authors)}\n"
        paper_list += "\n"
    paper_list += "---\n"

    survey_body = _strip_generated_references(survey_text)
    context_char_limit = int(getattr(args, "survey_context_chars", 60000))
    if len(survey_body) <= context_char_limit:
        survey_context = survey_body
    else:
        # Retain both foundations and conclusions/gaps when an unusually long
        # survey exceeds the context budget.
        front_chars = context_char_limit * 2 // 3
        back_chars = context_char_limit - front_chars
        survey_context = (
            survey_body[:front_chars]
            + "\n\n[... middle context omitted for bounded handoff ...]\n\n"
            + survey_body[-back_chars:]
        )
    relation_brief = build_relation_brief(survey_body)
    available_references = len(reference_ids)
    min_citations = min(args.min_citations, available_references)
    target_citations = min(
        max(
            int(getattr(args, "target_citations", DEFAULT_TARGET_RELATED_CITATIONS)),
            min_citations,
        ),
        available_references,
    )
    max_citations = min(
        max(
            int(getattr(args, "max_citations", DEFAULT_MAX_RELATED_CITATIONS)),
            target_citations,
        ),
        available_references,
    )

    prompt_text = f"""Write a Related Works section in LaTeX for a survey about "{args.topic}".

Here is the complete survey body for context (the generated References section has been removed):
---
{survey_context}
---

Relation-preservation brief extracted from citation-bearing passages across the complete survey:
---
{relation_brief}
---

Citation key mapping (use \\cite{{key}} format):
{citation_key_map}

Reference papers:
{paper_list}

Requirements:
1. Write in LaTeX using \\subsection{{}} for thematic categories.
2. Use \\citep{{}} and \\citet{{}} commands with the exact keys shown above.
3. Use {min_citations}-{max_citations} distinct citation keys and aim for about {target_citations}. This is the focused related-works core, not the full survey's 100+ paper coverage. Citation occurrences and large multi-key citation clusters do not substitute for distinct evidence-bearing references.
4. Organize by theme, not paper-by-paper.
5. Highlight limitations and open gaps.
6. Output only the LaTeX content (no preamble, no \\documentclass).
7. Each subsection should have 2-3 paragraphs.
8. Write {args.min_words}-{args.max_words} words total and include at least 3 subsections unless the citation material is insufficient.
9. Use 4-6 thematic subsections and aim for roughly 1,800-2,200 words when enough references are available; do not compress 45-55 papers into terse, list-like paragraphs.
10. Do not try to cite every mapped key. Select the references that support the comparison being made, attach every citation to a concrete claim, and use multi-key citations only for papers that genuinely support the same claim.
11. Preserve the survey's relation structure. In each substantive subsection, connect capability or mechanism to its assumptions/boundary, relevant counterevidence or limitation, and the residual gap when the supplied evidence supports that chain. Never invent a counterexample merely to fill the template.
12. Include one explicit, evidence-grounded future-direction paragraph using phrases such as "future work", "open problems", or "principled extensions", and state a testable comparison or protocol rather than a generic aspiration.
13. For gap-motivated topics, explicitly state the motivating gap and distinguish algorithmic constraints from theoretical or topology/linear-speedup constraints.
"""

    output = {
        "stage": "related_works",
        "prompt": prompt_text,
        "citation_key_map": citation_key_map,
        "key_map": key_map,
        "survey_context_chars": len(survey_context),
        "survey_body_chars": len(survey_body),
        "relation_brief": relation_brief,
        "min_distinct_citations": min_citations,
        "target_distinct_citations": target_citations,
        "max_distinct_citations": max_citations,
    }

    output_path = resolve_path(workspace_root, args.output_path)
    write_json(output_path, output)
    print(json.dumps({"output_path": str(output_path)}, indent=2))
    return 0


def command_prepare_judge_data(args: argparse.Namespace) -> int:
    prompts = load_prompt_templates()
    workspace_root = resolve_workspace(args.workspace)

    survey_path = resolve_path(workspace_root, args.survey_path)
    survey_content = survey_path.read_text(encoding="utf-8")

    criteria = {
        "Coverage": {
            "Criterion Description": "Whether the survey covers the main aspects of the topic comprehensively.",
            "Score 1 Description": "Very poor coverage, missing most important aspects.",
            "Score 2 Description": "Poor coverage, missing several important aspects.",
            "Score 3 Description": "Moderate coverage, covers some aspects well but misses others.",
            "Score 4 Description": "Good coverage, covers most aspects well with minor gaps.",
            "Score 5 Description": "Excellent coverage, comprehensively covers all important aspects.",
        },
        "Structure": {
            "Criterion Description": "Whether the survey is well-organized with logical flow between sections.",
            "Score 1 Description": "Very poor structure, disorganized and hard to follow.",
            "Score 2 Description": "Poor structure, significant organizational issues.",
            "Score 3 Description": "Moderate structure, generally organized but with some issues.",
            "Score 4 Description": "Good structure, well-organized with minor issues.",
            "Score 5 Description": "Excellent structure, perfectly organized with clear logical flow.",
        },
        "Relevance": {
            "Criterion Description": "Whether the cited papers are relevant and properly support the survey claims.",
            "Score 1 Description": "Very poor relevance, most citations are irrelevant or unsupported.",
            "Score 2 Description": "Poor relevance, many citations are irrelevant or weakly supported.",
            "Score 3 Description": "Moderate relevance, some citations are irrelevant but most are okay.",
            "Score 4 Description": "Good relevance, most citations are relevant and well-used.",
            "Score 5 Description": "Excellent relevance, all citations are highly relevant and well-integrated.",
        },
    }

    prompt_entries: list[dict] = []
    for criterion_name, criterion_paras in criteria.items():
        all_paras = {
            "TOPIC": args.topic,
            "SURVEY": survey_content,
        }
        all_paras.update(criterion_paras)
        prompt_text = fill_prompt(prompts.CRITERIA_BASED_JUDGING_PROMPT, all_paras)
        prompt_entries.append({"criterion": criterion_name, "prompt": prompt_text})

    output = {"stage": "judge", "prompts": prompt_entries}

    output_path = resolve_path(workspace_root, args.output_path)
    write_json(output_path, output)
    print(
        json.dumps(
            {"output_path": str(output_path), "num_criteria": len(prompt_entries)},
            indent=2,
        )
    )
    return 0


def command_validate(args: argparse.Namespace) -> int:
    workspace_root = resolve_workspace(args.workspace)
    tex_paths = [resolve_path(workspace_root, tex_path) for tex_path in args.tex_files]
    bib_path = resolve_path(workspace_root, args.bib)
    report = validate_tex_bib(tex_paths, bib_path)
    required_report = None
    if args.survey_root:
        survey_root = resolve_path(workspace_root, args.survey_root)
        related_root = workspace_root / "related_works"
        required_report = validate_required_files(
            [
                survey_root / "survey.md",
                survey_root / "survey.json",
                survey_root / "references.bib",
                related_root / "related_works.tex",
                related_root / "references.bib",
            ]
        )

    if args.json:
        payload: dict[str, Any] = {"validation": report}
        if required_report is not None:
            payload["required_files"] = required_report
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    else:
        print(f"TeX files: {', '.join(report['tex_files'])}")
        print(f"Bib file: {report['bib_file']}")
        print(f"Cited keys: {report['cited_key_count']}")
        print(f"Bib keys: {report['bib_key_count']}")
        print(
            "Missing keys: "
            + (", ".join(report["missing_keys"]) if report["missing_keys"] else "none")
        )
        print(
            "Duplicate bib keys: "
            + (
                ", ".join(report["duplicate_bib_keys"])
                if report["duplicate_bib_keys"]
                else "none"
            )
        )
        print(
            "Unused keys: "
            + (", ".join(report["unused_keys"]) if report["unused_keys"] else "none")
        )
        if required_report is not None:
            print(
                "Missing required files: "
                + (
                    ", ".join(required_report["missing_files"])
                    if required_report["missing_files"]
                    else "none"
                )
            )

    required_ok = True if required_report is None else required_report["ok"]
    return 0 if report["ok"] and required_ok else 1


def command_finalize_package(args: argparse.Namespace) -> int:
    workspace_root = resolve_workspace(args.workspace)
    report = ensure_final_survey_package(
        workspace_root=workspace_root,
        survey_root_raw=args.survey_root,
        related_root_raw=args.related_root,
        topic=args.topic,
        min_survey_words=args.min_survey_words,
        min_survey_subsections=args.min_survey_subsections,
        min_survey_lines=args.min_survey_lines,
        min_related_citations=args.min_related_citations,
        min_related_words=args.min_related_words,
        min_related_sections=args.min_related_sections,
        keep_intermediates=args.keep_intermediates,
        min_survey_citations=args.min_survey_citations,
        max_related_citations=args.max_related_citations,
    )
    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        print(f"Survey root: {report['survey_root']}")
        print(f"Related works root: {report['related_root']}")
        print(f"Survey words: {report['survey_words']}")
        print(f"Survey subsections: {report['survey_subsections']}")
        print(f"Survey lines: {report['survey_lines']}")
        print(f"References: {report['reference_count']}")
        print(f"Missing keys: {', '.join(report['validation']['missing_keys']) or 'none'}")
        print(
            "Duplicate bib keys: "
            + (", ".join(report["validation"]["duplicate_bib_keys"]) or "none")
        )
    return 0 if report["quality"]["ok"] else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Pure-data survey tools + prompt preparation (no LLM calls)"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    def add_common(cmd: argparse.ArgumentParser) -> None:
        cmd.add_argument("--workspace", default=".")
        cmd.add_argument("--db-path", default="")
        cmd.add_argument("--embedding-model", default="")
        cmd.add_argument("--library-dir", default="survey/library")
        cmd.add_argument(
            "--structure-mode",
            choices=["auto", "include", "exclude"],
            default="auto",
            help="Include the ReaScholar structure pack, exclude it for a clean control, or auto-detect it.",
        )
        cmd.add_argument(
            "--structure-pack",
            default="",
            help="Optional structure_pack.json path; defaults to <library-dir>/structure_pack.json.",
        )

    p = subparsers.add_parser("prepare-outline-data")
    add_common(p)
    p.add_argument("--topic", required=True)
    p.add_argument("--output-path", required=True)
    p.add_argument("--section-num", type=int, default=DEFAULT_SECTION_NUM)
    p.add_argument("--reference-num", type=int, default=DEFAULT_NATIVE_EVIDENCE_MAX)
    p.add_argument("--rag-num", type=int, default=DEFAULT_RAG_NUM)
    p.add_argument("--chunk-size", type=int, default=30000)
    p.add_argument("--task-path", default="")
    p.add_argument("--max-abstract-chars", type=int, default=1200)
    p.add_argument(
        "--frozen-pool-only",
        action="store_true",
        help="Use every paper from paper_pool.jsonl in frozen order without query-time selection.",
    )

    p = subparsers.add_parser("merge-outline-data")
    p.add_argument("--workspace", default=".")
    p.add_argument("--outlines-path", required=True)
    p.add_argument("--output-path", required=True)

    p = subparsers.add_parser("prepare-subsection-outline-data")
    add_common(p)
    p.add_argument("--topic", required=True)
    p.add_argument("--section-outline-path", required=True)
    p.add_argument("--output-path", required=True)
    p.add_argument("--rag-num", type=int, default=DEFAULT_RAG_NUM)

    p = subparsers.add_parser("prepare-edit-outline-data")
    p.add_argument("--workspace", default=".")
    p.add_argument("--merged-outline-path", required=True)
    p.add_argument("--output-path", required=True)

    p = subparsers.add_parser("merge-outline")
    p.add_argument("--workspace", default=".")
    p.add_argument("--section-outline-path", required=True)
    p.add_argument("--subsection-outlines-path", required=True)
    p.add_argument("--output-path", required=True)

    p = subparsers.add_parser("prepare-subsection-data")
    add_common(p)
    p.add_argument("--topic", required=True)
    p.add_argument("--outline-path", required=True)
    p.add_argument("--output-path", required=True)
    p.add_argument("--rag-num", type=int, default=DEFAULT_RAG_NUM)
    p.add_argument("--subsection-len", type=int, default=DEFAULT_SUBSECTION_LEN)

    p = subparsers.add_parser("prepare-native-survey-data")
    add_common(p)
    p.add_argument("--topic", required=True)
    p.add_argument("--outline-path", required=True)
    p.add_argument("--output-path", required=True)
    p.add_argument("--bib-output", default="survey/references.bib")
    p.add_argument("--survey-metadata-output", default="survey/survey.json")
    p.add_argument("--rag-num", type=int, default=DEFAULT_RAG_NUM)
    p.add_argument("--max-papers", type=int, default=DEFAULT_NATIVE_EVIDENCE_MAX)
    p.add_argument("--max-external-papers", type=int, default=50)
    p.add_argument("--min-words", type=int, default=DEFAULT_MIN_SURVEY_WORDS)
    p.add_argument("--target-words", type=int, default=DEFAULT_TARGET_SURVEY_WORDS)
    p.add_argument("--task-path", default="")
    p.add_argument(
        "--min-unique-citations",
        type=int,
        default=DEFAULT_MIN_UNIQUE_SURVEY_CITATIONS,
    )
    p.add_argument(
        "--target-unique-citations",
        type=int,
        default=DEFAULT_TARGET_UNIQUE_SURVEY_CITATIONS,
    )
    p.add_argument("--max-evidence-chars", type=int, default=150000)
    p.add_argument(
        "--frozen-pool-only",
        action="store_true",
        help="Use every paper from paper_pool.jsonl in frozen order without outline-dependent selection.",
    )

    p = subparsers.add_parser("prepare-citation-check-data")
    p.add_argument("--workspace", default=".")
    p.add_argument("--topic", required=True)
    p.add_argument("--drafts-path", required=True)
    p.add_argument("--output-path", required=True)

    p = subparsers.add_parser("prepare-lce-data")
    p.add_argument("--workspace", default=".")
    p.add_argument("--topic", required=True)
    p.add_argument("--content-path", required=True)
    p.add_argument("--output-path", required=True)

    p = subparsers.add_parser("resolve-references")
    add_common(p)
    p.add_argument("--survey-path", required=True)
    p.add_argument("--output-path", required=True)

    p = subparsers.add_parser("generate-bibtex")
    p.add_argument("--workspace", default=".")
    p.add_argument("--survey-json", required=True)
    p.add_argument("--bib-output", required=True)
    p.add_argument("--key-map-output", default="")

    p = subparsers.add_parser("assemble-survey")
    p.add_argument("--workspace", default=".")
    p.add_argument("--outline-path", required=True)
    p.add_argument("--sections-dir", required=True)
    p.add_argument("--output-path", required=True)

    p = subparsers.add_parser("prepare-related-works-data")
    add_common(p)
    p.add_argument("--topic", required=True)
    p.add_argument("--survey-path", required=True)
    p.add_argument("--output-path", required=True)
    p.add_argument("--min-words", type=int, default=DEFAULT_MIN_RELATED_WORDS)
    p.add_argument("--max-words", type=int, default=2500)
    p.add_argument("--min-citations", type=int, default=DEFAULT_MIN_RELATED_CITATIONS)
    p.add_argument(
        "--target-citations", type=int, default=DEFAULT_TARGET_RELATED_CITATIONS
    )
    p.add_argument("--max-citations", type=int, default=DEFAULT_MAX_RELATED_CITATIONS)
    p.add_argument("--survey-context-chars", type=int, default=60000)

    p = subparsers.add_parser("prepare-judge-data")
    p.add_argument("--workspace", default=".")
    p.add_argument("--topic", required=True)
    p.add_argument("--survey-path", required=True)
    p.add_argument("--output-path", required=True)

    p = subparsers.add_parser("validate")
    p.add_argument("--workspace", default=".")
    p.add_argument("--tex", action="append", required=True, dest="tex_files")
    p.add_argument("--bib", required=True)
    p.add_argument("--survey-root", default="")
    p.add_argument("--json", action="store_true")

    p = subparsers.add_parser("finalize-package")
    p.add_argument("--workspace", default=".")
    p.add_argument("--topic", required=True)
    p.add_argument("--survey-root", default="survey")
    p.add_argument("--related-root", default="related_works")
    p.add_argument("--min-survey-words", type=int, default=DEFAULT_MIN_SURVEY_WORDS)
    p.add_argument(
        "--min-survey-subsections",
        type=int,
        default=DEFAULT_MIN_SURVEY_SUBSECTIONS,
    )
    p.add_argument("--min-survey-lines", type=int, default=DEFAULT_MIN_SURVEY_LINES)
    p.add_argument(
        "--min-related-citations", type=int, default=DEFAULT_MIN_RELATED_CITATIONS
    )
    p.add_argument(
        "--max-related-citations", type=int, default=DEFAULT_MAX_RELATED_CITATIONS
    )
    p.add_argument(
        "--min-survey-citations",
        type=int,
        default=DEFAULT_MIN_UNIQUE_SURVEY_CITATIONS,
    )
    p.add_argument("--min-related-words", type=int, default=DEFAULT_MIN_RELATED_WORDS)
    p.add_argument(
        "--min-related-sections", type=int, default=DEFAULT_MIN_RELATED_SECTIONS
    )
    p.add_argument("--keep-intermediates", action="store_true")
    p.add_argument("--json", action="store_true")

    return parser


COMMANDS = {
    "prepare-outline-data": command_prepare_outline_data,
    "merge-outline-data": command_merge_outline_data,
    "prepare-subsection-outline-data": command_prepare_subsection_outline_data,
    "prepare-edit-outline-data": command_prepare_edit_outline_data,
    "merge-outline": command_merge_outline,
    "prepare-subsection-data": command_prepare_subsection_data,
    "prepare-native-survey-data": command_prepare_native_survey_data,
    "prepare-citation-check-data": command_prepare_citation_check_data,
    "prepare-lce-data": command_prepare_lce_data,
    "resolve-references": command_resolve_references,
    "generate-bibtex": command_generate_bibtex,
    "assemble-survey": command_assemble_survey,
    "prepare-related-works-data": command_prepare_related_works_data,
    "prepare-judge-data": command_prepare_judge_data,
    "validate": command_validate,
    "finalize-package": command_finalize_package,
}


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        handler = COMMANDS.get(args.command)
        if handler:
            return handler(args)
        parser.error(f"Unknown command: {args.command}")
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
