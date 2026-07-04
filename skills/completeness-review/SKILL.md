---
name: completeness-review
description: Use when judging whether a paper draft is complete enough to hand off, submit, or move into final polishing
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

# Completeness Review

## Overview
Completeness means every promised part of the paper exists and every major claim has visible support. Use deterministic checks before qualitative review.

## Helper Script
Set `SKILL_ROOT="$REASFLOW_SKILLS_ROOT/completeness-review"`.

```bash
python3 "$SKILL_ROOT/scripts/review-manuscript.py" --project-dir paper --main-file main.tex
```

Then pair it with:

```bash
python3 "$REASFLOW_SKILLS_ROOT/check-asset-usage/scripts/check_asset_usage.py" \
  --assets-dir assets \
  --output-dir paper
```

## Checklist
1. Verify all required sections and appendices exist.
2. Confirm every contribution claim has supporting proof, experiment, or citation.
3. Check figure, table, bibliography, and asset coverage.
4. Mark what is missing, weak, or still placeholder text.

## Deliverables
- readiness verdict
- must-fix list before handoff
- optional polish list for later passes
