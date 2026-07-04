---
name: citation-hygiene
description: Use when checking citation coverage, unsupported claims, bibliography consistency, or missing attribution in research writing
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

# Citation Hygiene

## Overview
Enforce cite/bib consistency and flag claim-like lines that may need citations before submission.

## Installed Paths
Set:

```bash
SKILL_ROOT="$REASFLOW_SKILLS_ROOT/citation-hygiene"
```

## Helper Commands
Run cite/bib and claim checks:

```bash
python3 "$SKILL_ROOT/scripts/check_citation_hygiene.py" \
  --project-dir output/Paper03_SudaMuon \
  --main-file main.tex \
  --format text
```

Allow unused BibTeX entries while still failing on missing cite keys:

```bash
python3 "$SKILL_ROOT/scripts/check_citation_hygiene.py" \
  --project-dir output/Paper03_SudaMuon \
  --allow-unused \
  --format json
```

Python env fallback:

```bash
uv run "$SKILL_ROOT/scripts/check_citation_hygiene.py" \
  --project-dir output/Paper03_SudaMuon --format text
```

## Expected Output
- missing citation keys (`\cite` in TeX but absent in `.bib`)
- duplicate BibTeX keys
- optional unused bib key list
- unsupported claim candidates (file + line + section)

## Deliverables
- unsupported-claim list
- bibliography cleanup list
- sections still missing citation coverage
