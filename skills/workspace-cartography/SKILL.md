---
name: workspace-cartography
description: Use when entering an unfamiliar research or code workspace and needing a fast map of folders, artifacts, and ownership boundaries
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

# Workspace Cartography

## Overview
Build a practical map before deep work. The goal is to identify where code, paper sources, experiments, data, and generated outputs live.

## Scan Order
1. Read top-level docs, configs, and build entrypoints first.
2. Note directories for source, paper drafts, experiments, figures, data, and logs.
3. Separate hand-written files from generated outputs.
4. Record commands for build, test, and paper compilation.
5. Surface missing or ambiguous ownership boundaries before editing.

## Deliverables
- directory map with purpose for major folders
- key commands and entrypoints
- risk notes for generated artifacts or unclear source of truth
