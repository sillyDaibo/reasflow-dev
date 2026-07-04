---
name: abstract-alignment
description: Use when checking that the abstract matches the introduction, method, experiments, and actual evidence in the paper
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

# Abstract Alignment

## Overview
The abstract is a compression of the paper, not a wish list. Every claim should map cleanly to material that already exists in the draft.

## Checklist
1. Verify the problem, method, and result claims all appear in the body.
2. Mark unsupported claims with `anti-hallucination-markers` before polishing them away.
3. Remove novelty or performance claims that lack evidence.
4. Keep terminology aligned with the introduction and conclusion.
5. Make sure the final sentence matches the real significance of the work.

## Deliverables
- aligned abstract draft
- body sections that support each sentence
- claims to delete or downgrade
