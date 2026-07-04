#!/usr/bin/env python3
"""Write an academic paper Introduction section (LaTeX + BibTeX).

Migrated from agentscope-intro-main/agentscope_intro/tools/intro_tools.py.
Adapted for OpenCode: CLI interface, stream=True, User-Agent header, env-var config.
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

# ---------------------------------------------------------------------------
# Style templates
# ---------------------------------------------------------------------------

ML_TEMPLATE = """
Structure for Machine Learning / Deep Learning / AI papers (NeurIPS/ICML/ICLR style):
1. Hook (1-2 sentences): Striking observation or key motivation.
2. Background (2-3 sentences): Research context and problem definition.
3. Gap (2-3 sentences): Limitations of existing methods — what is missing.
4. Our Approach (2-3 sentences): What this paper does and how.
5. Contributions (3-5 bullets): Concrete, evidence-backed claims.
Rules: Emphasize experimental results, performance comparisons, practical applications.
""".strip()

MATH_TEMPLATE = """
Structure for Applied Mathematics / Optimization papers (SIAM / Mathematical Programming style):
1. Hook (1-2 sentences): Research motivation.
2. Objective (2-3 sentences): Formal problem statement with math notation.
3. Background (2-3 sentences): Mathematical context and prior work overview.
4. Related Work (3-4 sentences): Categorized prior work with gaps.
5. Gap (2-3 sentences): What is unsolved or missing in the literature.
6. Contributions (3-5 bullets): Theoretical results and innovations.
7. Notation (1-2 sentences): Key symbols and conventions.
8. Organization (1-2 sentences): Paper structure overview.
Rules: Include formal notation, problem formulation, convergence/complexity results.
""".strip()

DEFAULT_TEMPLATE = """
Structure for General CS papers:
1. Hook (1-2 sentences): Motivation.
2. Background (2-3 sentences): Context.
3. Survey (2-3 sentences): Related work overview.
4. Gap (2-3 sentences): Unresolved issues.
5. Contributions (3-5 bullets): This paper's answers.
""".strip()

SYSTEM_PROMPT = """You are a senior academic writing assistant specializing in mathematical optimization and machine learning papers.
Your task is to write a high-quality Introduction section in LaTeX format.

Output format — return ONLY the following two sections, clearly delimited:

===TEX_START===
[Full LaTeX Introduction section content — no \\begin{{document}} wrapper]
===TEX_END===

===BIB_START===
[BibTeX entries for all cited papers — empty block if none]
===BIB_END===

Anti-hallucination rules:
- Every factual claim must be supported by the provided information.
- Mark unverifiable claims with % [VERIFY: <claim>] comments.
- Do not invent paper titles, authors, or results.
- If bib_content is provided, reuse those exact BibTeX keys and entries.
"""


def _build_prompt(
    title: str,
    problem_background: str,
    related_works: str,
    method_summary: str,
    style: str,
    results_preview: str,
    user_feedback: str,
    bib_content: str,
) -> str:
    template = {"ml": ML_TEMPLATE, "math": MATH_TEMPLATE}.get(style, DEFAULT_TEMPLATE)
    parts = [
        f"Paper title: {title}",
        f"\nWriting style: {style}",
        f"\nTemplate structure:\n{template}",
        f"\nProblem background:\n{problem_background}",
        f"\nRelated works:\n{related_works}",
        f"\nMethod summary:\n{method_summary}",
    ]
    if results_preview:
        parts.append(f"\nKey results (optional):\n{results_preview}")
    if bib_content:
        parts.append(f"\nExisting BibTeX (reuse these keys):\n{bib_content}")
    if user_feedback:
        parts.append(f"\nRevision feedback:\n{user_feedback}")
    parts.append("\nNow write the Introduction section following the template above.")
    return "\n".join(parts)


def _call_llm(prompt: str, base_url: str, api_key: str, model: str) -> str:
    payload = json.dumps({
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        "stream": True,
    }).encode("utf-8")
    request = urllib.request.Request(
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
    with urllib.request.urlopen(request, timeout=180) as response:
        for raw_line in response:
            line = raw_line.decode("utf-8").strip()
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


def _parse_response(text: str) -> tuple[str, str]:
    tex_match = re.search(r"===TEX_START===(.*?)===TEX_END===", text, re.DOTALL)
    bib_match = re.search(r"===BIB_START===(.*?)===BIB_END===", text, re.DOTALL)
    tex = tex_match.group(1).strip() if tex_match else text.strip()
    bib = bib_match.group(1).strip() if bib_match else ""
    return tex, bib


def _make_main_tex(tex_output_path: str, bib_output_path: str) -> str:
    tex_rel = Path(tex_output_path).name
    bib_rel = Path(bib_output_path).stem
    return rf"""\documentclass{{article}}
\usepackage{{amsmath,amssymb,amsthm}}
\usepackage{{hyperref}}
\usepackage{{natbib}}
\begin{{document}}
\input{{{tex_rel}}}
\bibliographystyle{{plainnat}}
\bibliography{{{bib_rel}}}
\end{{document}}
"""


def main() -> int:
    parser = argparse.ArgumentParser(description="Write academic Introduction (LaTeX)")
    parser.add_argument("--title", required=True)
    parser.add_argument("--problem-background", required=True)
    parser.add_argument("--related-works", required=True)
    parser.add_argument("--method-summary", required=True)
    parser.add_argument("--tex-output", required=True, help="Output .tex path")
    parser.add_argument("--bib-output", required=True, help="Output .bib path")
    parser.add_argument("--style", default="default", choices=["ml", "math", "default"])
    parser.add_argument("--results-preview", default="")
    parser.add_argument("--user-feedback", default="")
    parser.add_argument("--bib-input", default="", help="Existing .bib file to reuse")
    parser.add_argument("--generate-main", action="store_true", default=True)
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--api-key", default=DEFAULT_API_KEY)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    args = parser.parse_args()

    if not args.api_key:
        print("ERROR: OPENAI_API_KEY not set", file=sys.stderr)
        return 1

    bib_content = ""
    if args.bib_input and Path(args.bib_input).exists():
        bib_content = Path(args.bib_input).read_text(encoding="utf-8")

    prompt = _build_prompt(
        title=args.title,
        problem_background=args.problem_background,
        related_works=args.related_works,
        method_summary=args.method_summary,
        style=args.style,
        results_preview=args.results_preview,
        user_feedback=args.user_feedback,
        bib_content=bib_content,
    )

    try:
        response_text = _call_llm(prompt, args.base_url, args.api_key, args.model)
    except Exception as exc:
        print(f"ERROR: LLM call failed: {exc}", file=sys.stderr)
        return 1

    tex_content, bib_content_out = _parse_response(response_text)

    tex_path = Path(args.tex_output)
    bib_path = Path(args.bib_output)
    tex_path.parent.mkdir(parents=True, exist_ok=True)
    bib_path.parent.mkdir(parents=True, exist_ok=True)

    tex_path.write_text(tex_content, encoding="utf-8")
    bib_path.write_text(bib_content_out, encoding="utf-8")

    output: dict[str, object] = {
        "tex_output": str(tex_path),
        "bib_output": str(bib_path),
    }

    if args.generate_main:
        main_path = tex_path.parent / "main.tex"
        main_path.write_text(
            _make_main_tex(args.tex_output, args.bib_output), encoding="utf-8"
        )
        output["main_tex"] = str(main_path)

    print(json.dumps(output, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
