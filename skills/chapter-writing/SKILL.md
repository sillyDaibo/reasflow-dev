---
name: chapter-writing
description: Use when a chapter owner must turn assigned assets into publication-ready LaTeX without drifting beyond the assigned file
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

# Chapter Writing

## Overview
This skill supports `paper-subwriter` after the assignment contract is already fixed by the prompt. It does not define chapter ownership; it tells the writer how to consume assigned assets correctly.

## Installed Paths
Set:

```bash
SKILL_ROOT="$REASFLOW_SKILLS_ROOT/chapter-writing"
```

## Asset Handling Rules
1. `.tex`: copy the content directly when possible, preserve environments and `\label{}` tags, and only lightly adapt surrounding connective prose.
2. `.bib`, `.yaml`, `.yml`: keep citation keys stable, merge entries into the chapter-local bibliography flow only when the assignment requests it, and never invent keys.
3. images: wrap in `figure` environments with `\caption{}` and `\label{fig:...}`, then reference them in the text.
4. `.md` and `.txt`: convert the substance into academic prose; do not paste markdown syntax into LaTeX.
5. code and experiment reports: describe the algorithm, result, or setting they support; the paper normally cites the artifact outcome, not the source code itself.

## Helper Commands
Generate a chapter scaffold with section-level claim placeholders:

```bash
python3 "$SKILL_ROOT/scripts/create_chapter_draft.py" \
  --output output/Paper03_SudaMuon/theory.tex \
  --section "Problem Setup::Define setting, notation, and assumptions." \
  --section "Main Result::State theorem and proof roadmap." \
  --section "Proof::Provide complete proof with stable labels."
```

Python env fallback:

```bash
uv run python "$SKILL_ROOT/scripts/create_chapter_draft.py" \
  --output output/Paper03_SudaMuon/theory.tex \
  --section "Experiments::Summarize setup and key findings."
```

## Expected Output
- prints generated file path on success
- writes a `.tex` scaffold with section headers, claim comments, evidence checklist comments

## Workflow
1. Read only the assets named in the assignment.
2. Map each asset to a concrete paragraph, theorem block, figure, table, or bibliography entry in the output file.
3. Copy or lightly adapt source LaTeX rather than rewriting from memory.
4. Keep a running checklist so every assigned asset is consumed before handoff.

## Deliverables
- assigned chapter file
- asset-to-output mapping note
- missing-input list for `paper`
