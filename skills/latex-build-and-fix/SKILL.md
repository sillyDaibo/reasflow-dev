---
name: latex-build-and-fix
description: Use when building LaTeX papers, triaging compiler failures, or iterating on references, figures, and generated sections
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

# LaTeX Build And Fix

## Overview
Run robust multi-pass builds with parsed diagnostics. Fix the first root-cause failure, then rebuild until errors are gone and warnings are understood.

## Installed Paths
Set:

```bash
SKILL_ROOT="$REASFLOW_SKILLS_ROOT/latex-build-and-fix"
```

## Helper Commands
Wrapper (auto `python3`/`uv` fallback):

```bash
bash "$SKILL_ROOT/scripts/build-latex.sh" main.tex --project-dir output/Paper03_SudaMuon --format text
```

Explicit options:

```bash
python3 "$SKILL_ROOT/scripts/build_latex.py" main.tex \
  --project-dir output/Paper03_SudaMuon \
  --backend auto \
  --engine pdflatex \
  --bib-tool auto \
  --clean \
  --format json
```

Python env fallback:

```bash
uv run "$SKILL_ROOT/scripts/build_latex.py" main.tex --project-dir output/Paper03_SudaMuon --format text
```

## Expected Output
- build result with backend/engine and generated PDF path
- page count and elapsed seconds
- parsed errors/warnings plus warning type summary
- exact compile command trace for reproducibility

## Deliverables
- root-cause compile failure summary
- stable command sequence used
- warning backlog after successful build
