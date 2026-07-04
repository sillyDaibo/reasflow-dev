---
name: anti-hallucination-markers
description: Use when drafting introductions or abstracts that need explicit markers for unsupported claims, missing evidence, or scope drift
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

# Anti-Hallucination Markers

## Overview
Mark weak spots while drafting instead of letting them ship as confident prose. Unsupported novelty, performance, or scope claims should stay visibly flagged until evidence lands.

## Marker Set
- `[needs-citation]` for factual claims without a source
- `[needs-result]` for performance or ablation claims without experiment evidence
- `[scope-check]` for claims that overreach the actual setting
- `[terminology-check]` for wording that does not match the paper body
- `[remove-if-unproven]` for claims that may need deletion instead of repair

## Workflow
1. Draft the paragraph normally.
2. Tag every sentence that depends on evidence outside the current draft.
3. Resolve or delete marked claims before final polishing.
4. Remove markers only after the supporting section, figure, table, or citation is real.

## Deliverables
- marked-up intro or abstract draft
- evidence ledger for every flagged sentence
- deletion list for claims that stayed unsupported
