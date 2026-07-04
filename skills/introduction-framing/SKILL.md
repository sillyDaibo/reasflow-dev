---
name: introduction-framing
description: Use when framing an introduction around motivation, gap, approach, contributions, and reader expectations
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

# Introduction Framing

## Required pipeline

The intro agent must follow these steps in order. Manual file reading is not a substitute for the extraction scripts — the scripts produce structured JSON that prevents hallucination.

Set once:
```bash
SKILL_ROOT="$REASFLOW_SKILLS_ROOT/introduction-framing"
```

### 1. Extract from each source
Run one command per source type found in the workspace:

```bash
# Survey / related works / gap
python "$SKILL_ROOT/scripts/extract-workspace-info.py" \
  --mode survey --workspace . --source survey/survey.md \
  --output intro/survey_info.json

# Method description
python "$SKILL_ROOT/scripts/extract-workspace-info.py" \
  --mode method --workspace . --source Alg_Exp/document/method.md \
  --output intro/method_info.json

# Experiment results
python "$SKILL_ROOT/scripts/extract-workspace-info.py" \
  --mode experiment --workspace . --source Alg_Exp/experiment/results.md \
  --output intro/experiment_info.json

# Theory / proofs
python "$SKILL_ROOT/scripts/extract-workspace-info.py" \
  --mode theory --workspace . --source prover/proof.md \
  --output intro/theory_info.json
```

`--source` accepts a file or a directory (auto-scans `.md/.tex/.bib` up to depth 2).
All four modes are optional — only run modes for sources that exist.

### 2. Organize
```bash
python "$SKILL_ROOT/scripts/extract-workspace-info.py" \
  --mode organize \
  --inputs intro/survey_info.json intro/method_info.json \
  --output intro/organized_info.json
```
Pass only the `--inputs` files that were actually produced in step 1.

### 3. Write
Read `intro/organized_info.json`, then:
```bash
python "$SKILL_ROOT/scripts/write-introduction.py" \
  --title "Paper Title" \
  --problem-background "<organized_info.problem_background>" \
  --related-works "<organized_info.related_works>" \
  --method-summary "<organized_info.method_summary>" \
  --results-preview "<organized_info.results_preview>" \
  --style math \
  --bib-input survey/references.bib \
  --tex-output intro/introduction.tex \
  --bib-output intro/references.bib
```

`--style`: `ml` (machine learning), `math` (optimization/theory), `default` (other).
`--bib-input`: pass an existing `.bib` file when available; omit if none exists.
`--results-preview` and `--bib-input` are optional.

Both scripts read `OPENAI_BASE_URL`, `OPENAI_API_KEY`, `OPENAI_MODEL` from the environment.

## Deliverables
- `intro/introduction.tex` + `intro/references.bib`
- `intro/main.tex` (compilable wrapper)
- `intro/*_info.json` intermediate extraction files
- missing-evidence list for any fields that came back empty

