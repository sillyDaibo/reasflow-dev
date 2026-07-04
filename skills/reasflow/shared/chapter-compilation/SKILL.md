---
name: chapter-compilation
description: Use when compiling a single chapter in isolation or checking chapter-local LaTeX regressions before handoff
---

## Installed Root

Resolve the installed reasflow-dev skills root before running packaged scripts:

```bash
REASFLOW_SKILLS_ROOT="${REASFLOW_SKILLS_ROOT:-}"
if [ -z "$REASFLOW_SKILLS_ROOT" ]; then
  if [ -d ./.agents/skills ]; then
    REASFLOW_SKILLS_ROOT="$(pwd)/.agents/skills"
  elif [ -d "$HOME/.agents/skills" ]; then
    REASFLOW_SKILLS_ROOT="$HOME/.agents/skills"
  else
    echo "reasflow-dev skills not found in ./.agents/skills or $HOME/.agents/skills" >&2
    exit 1
  fi
fi
```

# Chapter Compilation

## Overview
This skill restores the original paper-agent behavior: compile one chapter independently without waiting for unrelated chapters to be finished.

## Installed Paths
Set:

```bash
SKILL_ROOT="$REASFLOW_SKILLS_ROOT/chapter-compilation"
```

## Helper Commands
Wrapper:

```bash
bash "$SKILL_ROOT/scripts/compile-chapter.sh" paper/main.tex paper/method.tex
```

Direct Python:

```bash
python3 "$SKILL_ROOT/scripts/compile_chapter.py" \
  --project-dir paper \
  --main-file main.tex \
  --chapter method.tex
```

Python env fallback:

```bash
uv run python "$SKILL_ROOT/scripts/compile_chapter.py" \
  --project-dir paper \
  --main-file main.tex \
  --chapter method.tex
```

## Output
The helper returns structured JSON with:
- `success`
- `pdf_path`
- `total_pages`
- `preview_images`
- `errors`
- `warnings`

## What The Helper Does
1. Extract preamble from `main.tex`.
2. Generate `_chapter_<name>.tex` with only the target `\input{...}`.
3. Compile via `latexmk` or manual engine plus BibTeX passes.
4. Parse compiler output into structured errors and warnings.
5. Render a small set of preview PNGs when local PDF tools are available.

## Deliverables
- isolated chapter compile status
- preview image paths for visual inspection when available
- explicit list of chapter-local errors to fix before handoff
