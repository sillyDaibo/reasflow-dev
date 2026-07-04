---
name: toy-verification
description: Use when stress-testing an algorithm or proof idea on tiny examples before committing to a full implementation or experiment
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

# Toy Verification

## Overview
Tiny examples expose hidden assumptions fast. Use them to verify the mechanism, not to claim final performance.

## Workflow
1. Build the smallest example that still exercises the core logic.
2. Work through expected behavior by hand.
3. Add one adversarial edge case.
4. Record what the toy example validates and what it cannot.

## Deliverables
- worked example with expected outputs
- edge-case note
- go or no-go recommendation for scaling up
