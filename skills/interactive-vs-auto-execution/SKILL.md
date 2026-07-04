---
name: interactive-vs-auto-execution
description: Use when deciding whether a domain workflow should pause for approval or continue unattended
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

# Interactive Vs Auto Execution

## Overview
Choose execution mode deliberately. Interactive runs pause at meaningful approval points; unattended runs keep moving with explicit assumptions and a clear audit trail.

## Interactive Mode
1. Stop when a choice would materially change scope, outputs, cost, or interpretation.
2. Present the recommended default plus the alternatives that matter.
3. Wait for confirmation before launching major downstream work.

## Unattended Mode
1. Continue only when the user explicitly asked not to wait or the current workflow says unattended execution is expected.
2. Pick the safest reasonable default from the prompt, workspace, and prior artifacts.
3. Record assumptions, default choices, and any follow-up checks needed in the handoff.

## Domain Reminders
- survey: lock topic framing, coverage axes, language, and outputs before full generation
- intro: verify title, style, and source evidence before drafting claims
- algorithm: surface ambiguous method choices before implementation and toy validation
- experiment: pause for expensive or controversial protocols unless unattended execution was requested
- paper: confirm template or chapter-map shifts before final assembly when a human is present
