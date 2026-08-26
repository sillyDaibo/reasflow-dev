---
name: survey-tex-bib-packaging
description: Use when producing survey and related-work LaTeX with synchronized references.bib
---

## Installed Root

Resolve the installed reasflow-dev private skills root before running packaged scripts:

```bash
REASFLOW_PRIVATE_SKILLS_ROOT="${REASFLOW_PRIVATE_SKILLS_ROOT:-}"
if [ -z "$REASFLOW_PRIVATE_SKILLS_ROOT" ]; then
  if [ -d ./.codex/reasflow-skills ]; then
    REASFLOW_PRIVATE_SKILLS_ROOT="$(pwd)/.codex/reasflow-skills"
  elif [ -d "$HOME/.codex/reasflow-skills" ]; then
    REASFLOW_PRIVATE_SKILLS_ROOT="$HOME/.codex/reasflow-skills"
  else
    echo "reasflow private skills not found in ./.codex/reasflow-skills or $HOME/.codex/reasflow-skills" >&2
    exit 1
  fi
fi
```

# Survey TeX and Bib Packaging

## Overview
Full survey deliveries are TeX-only publication packages. `survey/survey.tex` is the sole manuscript source; `survey/survey.pdf` is mandatory compiled evidence. The survey and related-work fragment share `survey/references.bib`.

This skill is the deterministic replacement for the cite/BibTeX validation slice of the upstream survey tooling. Pair it with native file inspection when you need to read or patch generated `.tex` files.

## Installed Paths
Set `SKILL_ROOT="$REASFLOW_PRIVATE_SKILLS_ROOT/survey/survey-tex-bib-packaging"` before invoking the packaged validator.

## Helper Script
- `python "$SKILL_ROOT/scripts/check-cite-bib.py" --tex survey/survey.tex --tex survey/related_works.tex --bib survey/references.bib`
- `python "$SKILL_ROOT/scripts/check-cite-bib.py" --tex survey/related_works.tex --bib survey/references.bib --json`
- `python "$SKILL_ROOT/scripts/build_publication.py" --workspace .`

## Rules
1. Generate `survey/survey.tex` directly. Do not deliver or retain `survey.md` as a second manuscript source.
2. Keep all `\\cite...{key}` usages aligned with BibTeX entry keys.
3. Use natbib-compatible citation commands (`\\citet`, `\\citep`, `\\citealp`) with `numbers,sort&compress`; avoid manually typed bracket numbers and repeated author-year text.
4. Keep references.bib as the single source of citation truth for survey outputs.
5. Flag missing keys instead of inventing citations.
6. The complete survey must cite at least 100 distinct, claim-bound papers. Related works targets 45-55 core papers.
7. Run the publication builder; compilation failure, duplicate BibTeX keys, missing keys, or citation-count gate failure means the delivery is incomplete.

## Deliverables
- `survey/survey.tex`
- `survey/references.bib`
- `survey/survey.pdf`
- `related_works/related_works.tex`
- `related_works/related_works.pdf`
- `build/publication_report.json`
