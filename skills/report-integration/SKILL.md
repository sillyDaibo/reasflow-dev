---
name: report-integration
description: Use when folding proofs, experiments, surveys, or writing progress back into a shared draft or status report
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

# Report Integration

## Overview
Integrate outputs while preserving provenance: every imported statement should map to a concrete source file or command result.

## Installed Paths
Set:

```bash
SKILL_ROOT="$REASFLOW_SKILLS_ROOT/report-integration"
```

## Helper Commands
Run reproducible command capture:

```bash
python3 "$SKILL_ROOT/scripts/execute_command.py" \
  --cwd output/Paper03_SudaMuon \
  --timeout 120 \
  --format text \
  "rg -n '\\\\cite' main.tex"
```

Merge multiple notes into one provenance-preserving report:

```bash
python3 "$SKILL_ROOT/scripts/integrate_report.py" \
  --output output/Paper03_SudaMuon/reports/integrated.md \
  --input output/Paper03_SudaMuon/reports/theory.md \
  --input output/Paper03_SudaMuon/reports/experiments.md \
  --input output/Paper03_SudaMuon/reports/review.md
```

Python env fallback:

```bash
uv run "$SKILL_ROOT/scripts/execute_command.py" --format json "ls -la"
uv run "$SKILL_ROOT/scripts/integrate_report.py" --output integrated.md --input note1.md
```

## Expected Output
- command helper: success flag, exit code, stdout/stderr, cwd
- report integrator: generated markdown path with source list and sectioned content

## Deliverables
- updated shared report file
- source path ledger for merged content
- unresolved conflict list
