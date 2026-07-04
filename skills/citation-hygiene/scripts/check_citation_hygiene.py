#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

CITE_PATTERN = re.compile(
    r"\\cite[a-zA-Z*]*\s*(?:\[[^\]]*\])?\s*(?:\[[^\]]*\])?\{([^}]*)\}"
)
BIB_PATTERN = re.compile(r"@\w+\s*\{\s*([^,\s]+)", re.IGNORECASE)
CLAIM_HINT_PATTERN = re.compile(
    r"\b(first|state[- ]of[- ]the[- ]art|outperform|significant(ly)?|novel|prove|superior)\b",
    re.IGNORECASE,
)
SECTION_PATTERN = re.compile(r"\\(?:section|subsection|subsubsection)\*?\{([^}]+)\}")


def strip_comments(line: str) -> str:
    if "%" not in line:
        return line
    escaped = re.sub(r"\\%", "", line)
    comment_index = escaped.find("%")
    if comment_index < 0:
        return line
    return line[:comment_index]


def collect_tex_files(main_tex: Path) -> list[Path]:
    project_dir = main_tex.parent
    visited: set[Path] = set()
    ordered: list[Path] = []

    def _walk(path: Path) -> None:
        resolved = path.resolve()
        if resolved in visited or not path.exists():
            return
        visited.add(resolved)
        ordered.append(path)
        content = path.read_text(encoding="utf-8", errors="replace")
        for match in re.finditer(r"\\(?:input|include)\{([^}]+)\}", content):
            ref = match.group(1).strip()
            child = project_dir / ref
            if not child.suffix:
                child = child.with_suffix(".tex")
            _walk(child)

    _walk(main_tex)
    return ordered


def parse_citations(tex_files: list[Path]) -> tuple[set[str], dict[str, list[str]]]:
    all_keys: set[str] = set()
    by_file: dict[str, list[str]] = {}
    for tex_file in tex_files:
        content = tex_file.read_text(encoding="utf-8", errors="replace")
        keys: set[str] = set()
        for match in CITE_PATTERN.finditer(content):
            for key in match.group(1).split(","):
                cleaned = key.strip()
                if cleaned:
                    keys.add(cleaned)
                    all_keys.add(cleaned)
        by_file[str(tex_file)] = sorted(keys)
    return all_keys, by_file


def parse_bib_keys(bib_paths: list[Path]) -> tuple[set[str], list[str]]:
    keys: set[str] = set()
    duplicates: list[str] = []
    for bib_path in bib_paths:
        content = bib_path.read_text(encoding="utf-8", errors="replace")
        for match in BIB_PATTERN.finditer(content):
            key = match.group(1).strip()
            if not key:
                continue
            if key in keys:
                duplicates.append(key)
            else:
                keys.add(key)
    return keys, sorted(set(duplicates))


def detect_unsupported_claims(tex_files: list[Path]) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    current_section = "(unknown)"
    for tex_file in tex_files:
        lines = tex_file.read_text(encoding="utf-8", errors="replace").splitlines()
        for index, raw_line in enumerate(lines, start=1):
            line = strip_comments(raw_line).strip()
            if not line:
                continue
            section_match = SECTION_PATTERN.search(line)
            if section_match:
                current_section = section_match.group(1).strip()

            has_claim_hint = bool(CLAIM_HINT_PATTERN.search(line))
            has_cite = bool(CITE_PATTERN.search(line))
            if has_claim_hint and not has_cite:
                findings.append(
                    {
                        "file": str(tex_file),
                        "line": index,
                        "section": current_section,
                        "text": line[:220],
                    }
                )
    return findings


def format_text(report: dict[str, Any]) -> str:
    lines = [
        "=== Citation Hygiene Report ===",
        f"main_tex: {report['main_tex']}",
        f"tex_files: {report['tex_file_count']}",
        f"bib_files: {report['bib_file_count']}",
        f"cited_keys: {report['cited_key_count']}",
        f"bib_keys: {report['bib_key_count']}",
        "",
    ]
    if report["missing_keys"]:
        lines.append(f"missing_keys ({len(report['missing_keys'])}): {', '.join(report['missing_keys'])}")
    else:
        lines.append("missing_keys: none")
    if report["unused_keys"]:
        lines.append(f"unused_keys ({len(report['unused_keys'])}): {', '.join(report['unused_keys'])}")
    else:
        lines.append("unused_keys: none")
    if report["duplicate_bib_keys"]:
        lines.append(
            f"duplicate_bib_keys ({len(report['duplicate_bib_keys'])}): {', '.join(report['duplicate_bib_keys'])}"
        )
    else:
        lines.append("duplicate_bib_keys: none")

    lines.append("")
    lines.append(f"unsupported_claim_candidates: {len(report['unsupported_claim_candidates'])}")
    for finding in report["unsupported_claim_candidates"][:10]:
        lines.append(
            f"  {finding['file']}:{finding['line']} [{finding['section']}] {finding['text']}"
        )
    if len(report["unsupported_claim_candidates"]) > 10:
        lines.append(
            f"  ... +{len(report['unsupported_claim_candidates']) - 10} more"
        )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Check citation hygiene: cite/bib consistency and unsupported claim hints."
    )
    parser.add_argument("--project-dir", default=".", help="Project directory containing main.tex.")
    parser.add_argument("--main-file", default="main.tex", help="Main TeX entry file.")
    parser.add_argument(
        "--bib",
        action="append",
        default=[],
        dest="bib_files",
        help="Explicit BibTeX file(s). If omitted, all *.bib under project-dir are scanned.",
    )
    parser.add_argument("--allow-unused", action="store_true", help="Do not fail on unused bib keys.")
    parser.add_argument("--format", choices=["text", "json"], default="text")
    args = parser.parse_args()

    project_dir = Path(args.project_dir).resolve()
    main_tex = project_dir / args.main_file
    if not main_tex.exists():
        print(f"Error: main TeX file not found: {main_tex}", file=sys.stderr)
        return 1

    tex_files = collect_tex_files(main_tex)
    if args.bib_files:
        bib_paths = [Path(path).resolve() for path in args.bib_files]
    else:
        bib_paths = sorted(project_dir.rglob("*.bib"))

    missing_bibs = [str(path) for path in bib_paths if not path.exists()]
    if missing_bibs:
        print(f"Error: missing bib file(s): {', '.join(missing_bibs)}", file=sys.stderr)
        return 1

    cited_keys, citations_by_file = parse_citations(tex_files)
    bib_keys, duplicate_keys = parse_bib_keys(bib_paths)
    missing_keys = sorted(cited_keys - bib_keys)
    unused_keys = sorted(bib_keys - cited_keys)
    unsupported_claims = detect_unsupported_claims(tex_files)

    report = {
        "main_tex": str(main_tex),
        "tex_file_count": len(tex_files),
        "bib_file_count": len(bib_paths),
        "citations_by_file": citations_by_file,
        "cited_key_count": len(cited_keys),
        "bib_key_count": len(bib_keys),
        "missing_keys": missing_keys,
        "unused_keys": unused_keys,
        "duplicate_bib_keys": duplicate_keys,
        "unsupported_claim_candidates": unsupported_claims,
    }

    if args.format == "json":
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(format_text(report))

    failed = bool(missing_keys or duplicate_keys or (unused_keys and not args.allow_unused))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
