#!/usr/bin/env python3
"""Validate and compile a TeX-only survey delivery with one bibliography."""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path


DEFAULT_TECTONIC = Path(
    "/home/iceysakura/lab/paper_gen/reasflow-workspaces/.toolchain/survey-pdf/tectonic"
)
CITE_PATTERN = re.compile(
    r"\\cite[a-zA-Z*]*\s*(?:\[[^\]]*\])?\s*(?:\[[^\]]*\])?\{([^}]*)\}"
)
BIB_PATTERN = re.compile(r"@\w+\s*\{\s*([^,\s]+)", re.IGNORECASE)


def citation_keys(text: str) -> set[str]:
    return {
        key.strip()
        for match in CITE_PATTERN.finditer(text)
        for key in match.group(1).split(",")
        if key.strip()
    }


def read_tex_tree(path: Path, root: Path, seen: set[Path] | None = None) -> str:
    """Expand local TeX inputs for validation without modifying the sources."""
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


def bibliography_keys(text: str) -> tuple[set[str], list[str]]:
    ordered = [match.group(1).strip() for match in BIB_PATTERN.finditer(text)]
    seen: set[str] = set()
    duplicates: list[str] = []
    for key in ordered:
        if key in seen and key not in duplicates:
            duplicates.append(key)
        seen.add(key)
    return seen, duplicates


def run_tectonic(tectonic: Path, tex_path: Path, build_dir: Path) -> dict:
    build_dir.mkdir(parents=True, exist_ok=True)
    command = [
        str(tectonic),
        "-X",
        "compile",
        str(tex_path),
        "--outdir",
        str(build_dir),
        "--keep-logs",
    ]
    result = subprocess.run(
        command,
        cwd=tex_path.parent,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    log_path = build_dir / f"{tex_path.stem}.build.log"
    log_path.write_text(result.stdout, encoding="utf-8")
    pdf_path = build_dir / f"{tex_path.stem}.pdf"
    return {
        "command": command,
        "returncode": result.returncode,
        "log": str(log_path),
        "pdf": str(pdf_path),
        "pdf_bytes": pdf_path.stat().st_size if pdf_path.exists() else 0,
        "ok": result.returncode == 0 and pdf_path.exists() and pdf_path.stat().st_size > 0,
    }


def standalone_related_tex() -> str:
    return r"""\documentclass[10pt,a4paper]{scrartcl}
\usepackage{fontspec}
\setmainfont{DejaVu Serif}
\usepackage{microtype}
\usepackage{amsmath,amssymb}
\usepackage{booktabs,longtable,graphicx,xcolor}
\usepackage[numbers,sort&compress]{natbib}
\usepackage[margin=22mm]{geometry}
\usepackage[colorlinks=true,linkcolor=black,citecolor=blue,urlcolor=blue]{hyperref}
\begin{document}
\section{Related Work}
\input{../related_works/related_works.tex}
\bibliographystyle{unsrtnat}
\bibliography{../references}
\end{document}
"""


def build(args: argparse.Namespace) -> dict:
    workspace = args.workspace.resolve()
    survey_dir = workspace / "survey"
    related_dir = workspace / "related_works"
    survey_tex = survey_dir / "survey.tex"
    related_tex = related_dir / "related_works.tex"
    bibliography = survey_dir / "references.bib"
    required = [survey_tex, related_tex, bibliography, args.tectonic]
    missing = [str(path) for path in required if not path.exists()]
    if missing:
        raise FileNotFoundError("missing publication inputs: " + ", ".join(missing))

    survey_entry_source = survey_tex.read_text(encoding="utf-8")
    related_entry_source = related_tex.read_text(encoding="utf-8")
    survey_source = read_tex_tree(survey_tex, survey_dir)
    related_source = read_tex_tree(related_tex, related_dir)
    bib_source = bibliography.read_text(encoding="utf-8")
    survey_keys = citation_keys(survey_source)
    related_keys = citation_keys(related_source)
    bib_keys, duplicate_bib_keys = bibliography_keys(bib_source)
    missing_survey_keys = sorted(survey_keys - bib_keys)
    missing_related_keys = sorted(related_keys - bib_keys)

    structural_errors: list[str] = []
    if "\\documentclass" not in survey_entry_source:
        structural_errors.append("survey.tex is not standalone: missing \\documentclass")
    if (
        "\\begin{document}" not in survey_entry_source
        or "\\end{document}" not in survey_entry_source
    ):
        structural_errors.append("survey.tex has incomplete document boundaries")
    related_has_class = "\\documentclass" in related_entry_source
    related_has_begin = "\\begin{document}" in related_entry_source
    related_has_end = "\\end{document}" in related_entry_source
    related_is_standalone = related_has_class and related_has_begin and related_has_end
    if related_has_class and not related_is_standalone:
        structural_errors.append(
            "standalone related_works.tex has incomplete document boundaries"
        )
    if not related_has_class and (related_has_begin or related_has_end):
        structural_errors.append(
            "fragment related_works.tex contains unmatched document boundaries"
        )

    validation = {
        "survey_distinct_citations": len(survey_keys),
        "survey_min_distinct_citations": args.min_survey_citations,
        "survey_coverage_ok": len(survey_keys) >= args.min_survey_citations,
        "related_distinct_citations": len(related_keys),
        "related_target_range": [args.min_related_citations, args.max_related_citations],
        "related_coverage_ok": args.min_related_citations
        <= len(related_keys)
        <= args.max_related_citations,
        "bib_entries": len(bib_keys),
        "duplicate_bib_keys": duplicate_bib_keys,
        "missing_survey_keys": missing_survey_keys,
        "missing_related_keys": missing_related_keys,
        "structural_errors": structural_errors,
        "related_source_format": (
            "standalone" if related_is_standalone else "embeddable_fragment"
        ),
    }
    validation["ok"] = not any(
        [
            duplicate_bib_keys,
            missing_survey_keys,
            missing_related_keys,
            structural_errors,
        ]
    ) and validation["survey_coverage_ok"] and validation["related_coverage_ok"]

    metadata_path = survey_dir / "survey.json"
    metadata = (
        json.loads(metadata_path.read_text(encoding="utf-8"))
        if metadata_path.exists()
        else {"schema_version": "tex-survey-v1"}
    )
    metadata.pop("survey", None)
    metadata.update(
        {
            "survey_tex_path": "survey.tex",
            "bibliography_path": "references.bib",
            "citation_keys_used": sorted(survey_keys),
            "distinct_citation_count": len(survey_keys),
            "publication_validation": validation,
        }
    )
    metadata_path.write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")

    build_root = workspace / "build"
    build_root.mkdir(parents=True, exist_ok=True)
    shared_bib = workspace / "references.bib"
    shutil.copyfile(bibliography, shared_bib)
    if not validation["ok"] and not args.compile_invalid:
        report = {"ok": False, "validation": validation, "compilation": {}}
        (build_root / "publication_report.json").write_text(
            json.dumps(report, indent=2) + "\n", encoding="utf-8"
        )
        return report

    if related_is_standalone:
        related_compile_source = related_tex
    else:
        related_compile_source = build_root / "related_works_standalone.tex"
        related_compile_source.write_text(standalone_related_tex(), encoding="utf-8")
    survey_compile = run_tectonic(args.tectonic, survey_tex, build_root / "survey")
    related_compile = run_tectonic(
        args.tectonic, related_compile_source, build_root / "related_works"
    )
    if survey_compile["ok"]:
        shutil.copyfile(survey_compile["pdf"], survey_dir / "survey.pdf")
    if related_compile["ok"]:
        shutil.copyfile(related_compile["pdf"], related_dir / "related_works.pdf")

    report = {
        "ok": validation["ok"] and survey_compile["ok"] and related_compile["ok"],
        "validation": validation,
        "compilation": {
            "tectonic": "0.17.0",
            "survey": survey_compile,
            "related_works": related_compile,
        },
    }
    (build_root / "publication_report.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8"
    )
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, default=Path("."))
    parser.add_argument("--tectonic", type=Path, default=DEFAULT_TECTONIC)
    parser.add_argument("--min-survey-citations", type=int, default=100)
    parser.add_argument("--min-related-citations", type=int, default=45)
    parser.add_argument("--max-related-citations", type=int, default=55)
    parser.add_argument("--compile-invalid", action="store_true")
    args = parser.parse_args()
    try:
        report = build(args)
    except FileNotFoundError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(report, indent=2))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
