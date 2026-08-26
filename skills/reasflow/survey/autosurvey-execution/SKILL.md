---
name: autosurvey-execution
description: Use when running the full AutoSurvey-backed outline, draft, related-works, or unattended survey pipeline
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
    echo "reasflow shared skills not found in ./.agents/skills or $HOME/.agents/skills" >&2
    exit 1
  fi
fi

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

# AutoSurvey Execution

## Overview
Run the AutoSurvey pipeline using Codex's configured model for all LLM work. Python handles data operations and prompt preparation; Codex survey subagents handle the actual drafting stages. The default full-survey contract is at least 10,000 words, a natural target around 12,000 words, and at least 100 distinct claim-bound papers. The focused Related Works contract is 45-55 core papers in roughly 1,800-2,200 words.

## Long-form organization

Use a publication-style argument, not a sequence of paper summaries:

1. Define the problem, notation, assumptions, and evaluation units for a technically capable beginner.
2. Establish a small set of orthogonal comparison axes, then organize 6-8 main sections and 24-32 substantive subsections around mechanisms and research questions.
3. Within each branch, explain lineage as motivating limitation, successor mechanism, changed assumption or guarantee, and remaining boundary.
4. Use compact tables to compare guarantees, communication or computation costs, deployment assumptions, and empirical regimes; the surrounding prose must interpret the table. Keep portrait tables to at most four concise columns. Use a landscape page for wider tables, account for inter-column padding when setting widths, and never place paragraph-length prose into narrow cells.
5. Close major branches with a synthesis paragraph before moving on. Ground gaps in source limitations, then check later work and counterevidence before proposing a testable future direction.

These rules reinforce the existing ReaScholar structure-pack design: taxonomy, timeline, limitations, later work, and future-work records become organizing evidence. They do not make Domain prose authoritative, replace primary-paper checks, or justify topic-irrelevant citations.

## Publication conventions

Use natbib citation commands with the numeric, sorted, compressed option. Write the package option exactly as `\\usepackage[numbers,sort&compress]{natbib}` with an unescaped ampersand. The rendered manuscript should show citations such as `[3--6]` and a numbered bibliography ordered by first citation. Citation keys remain internal and must never be printed as prose or URLs. Use a Unicode-safe XeTeX/fontspec preamble so author names and mathematical notation render without lossy substitutions.

Write narrative prose explicitly in each section. Never use a LaTeX macro to repeat sentences, paragraphs, subsection bodies, comparison boilerplate, or filler in order to reach a word threshold. Restrict custom macros to short mathematical notation. Treat repeated-prose macros as a publication-gate failure even if the expanded PDF passes the nominal word count.

## Architecture

Three layers:
1. **Python `autosurvey_tools.py`** — pure data operations + prompt preparation using AutoSurvey's original templates. Outputs JSON files with prepared prompts.
2. **Codex subagents** — `survey-outline`, `survey-section-writer`, `survey-related-works`, `survey-judge`.
3. **Workspace artifacts** — prompt JSON, internal outline, standalone survey LaTeX/PDF, related-work LaTeX/PDF, and one shared BibTeX source.

`batch_chat` maps to multiple `spawn_agent` calls, each followed by `wait_agent`.
`chat` maps to one `spawn_agent` + `wait_agent`.

Retrieval inside the writing stages prefers the local paper pool. When `--library-dir` (default `survey/library`) contains paper JSON produced by the `autosurvey-paper-retrieval` skill, `autosurvey_tools.py` builds an in-memory `ExternalPaperDatabase` from it and never touches AutoSurvey's embedding/Pinecone stack. AutoSurvey is only loaded as a fallback when the library is empty.

The four survey preparation commands also accept `--structure-mode auto|include|exclude` and optional `--structure-pack PATH`. `auto` injects a nonempty ReaScholar `structure_pack.json` when present, `include` requires it, and `exclude` creates a clean structure-free control while retaining the exact same paper library. Prompt JSON records both the structure hash/counts and frozen paper-pool hash.

## Environment
Set `SKILL_ROOT="$REASFLOW_PRIVATE_SKILLS_ROOT/survey/autosurvey-execution"`.
Use `python3` by default. If AutoSurvey dependencies such as `numpy` are missing, run the helper with the upstream environment:

```bash
python3 "$SKILL_ROOT/scripts/autosurvey_tools.py" ...
```

The helper script looks for AutoSurvey in this order:

1. `$AUTOSURVEY_ROOT`
2. `$AGENTSCOPE_SURVEY_ROOT/AutoSurvey`
3. `../meta-agent/modules/agentscope-survey/AutoSurvey` relative to the current workspace
4. `./AutoSurvey`

If dependencies are missing, use `uv` in the upstream checkout:

```bash
cd ../meta-agent/modules/agentscope-survey
uv sync
```

## Helper Script

`autosurvey_tools.py` provides these commands:

### Data + Prompt Preparation
- `python "$SKILL_ROOT/scripts/autosurvey_tools.py" prepare-outline-data --topic "..." --reference-num 140 --task-path frozen_task.yaml --max-abstract-chars 1200 --output-path survey/stage1.json`
- `python "$SKILL_ROOT/scripts/autosurvey_tools.py" merge-outline-data --outlines-path survey/outlines.json --output-path survey/stage2.json`
- `python "$SKILL_ROOT/scripts/autosurvey_tools.py" prepare-subsection-outline-data --topic "..." --section-outline-path survey/section_outline.md --output-path survey/stage3.json`
- `python "$SKILL_ROOT/scripts/autosurvey_tools.py" prepare-edit-outline-data --merged-outline-path survey/merged.md --output-path survey/stage4.json`
- `python "$SKILL_ROOT/scripts/autosurvey_tools.py" merge-outline --section-outline-path survey/section_outline.md --subsection-outlines-path survey/subsections.json --output-path survey/merged_outline.md`
- `python "$SKILL_ROOT/scripts/autosurvey_tools.py" prepare-subsection-data --topic "..." --outline-path survey/outline.md --output-path survey/stage5.json`
- `python "$SKILL_ROOT/scripts/autosurvey_tools.py" prepare-native-survey-data --topic "..." --outline-path survey/outline.md --max-papers 140 --min-words 10000 --target-words 12000 --min-unique-citations 100 --target-unique-citations 110 --max-evidence-chars 150000 --bib-output survey/references.bib --output-path survey/native_survey_prompt.json`
- `python "$SKILL_ROOT/scripts/autosurvey_tools.py" prepare-citation-check-data --topic "..." --drafts-path survey/drafts.json --output-path survey/cite_check.json`
- `python "$SKILL_ROOT/scripts/autosurvey_tools.py" prepare-lce-data --topic "..." --content-path survey/sections.json --output-path survey/lce.json`
- `python "$SKILL_ROOT/scripts/autosurvey_tools.py" assemble-survey --outline-path survey/outline.md --sections-dir survey/sections --output-path survey/survey_raw.md`
- `python "$SKILL_ROOT/scripts/autosurvey_tools.py" prepare-related-works-data --topic "..." --survey-path survey/survey.json --output-path related_works/rw_prompt.json`
- `python "$SKILL_ROOT/scripts/autosurvey_tools.py" prepare-judge-data --topic "..." --survey-path survey/survey.json --output-path survey/judge.json`
- `python "$SKILL_ROOT/scripts/autosurvey_tools.py" finalize-package --topic "..." --survey-root survey --related-root related_works --json`

### Validation
- `python "$SKILL_ROOT/scripts/autosurvey_tools.py" validate --workspace . --survey-root survey --tex survey/survey.tex --tex related_works/related_works.tex --bib survey/references.bib --json`

## Default Native Pipeline

Use this path first. It keeps AutoSurvey's retrieval, citation resolution, BibTeX rendering, and packaging guards, while letting the model write the survey as a coherent long-form artifact.

1. Create `survey/`, `survey/library/`, and `related_works/`.
2. Prepare and write an outline:
   - `prepare-outline-data` → `survey/stage1.json`
   - `spawn_agent` survey-outline with the prepared prompt, then `wait_agent` → `survey/outline.md`
3. Prepare one complete TeX survey-writing prompt and bibliography:
   - `prepare-native-survey-data --topic "..." --outline-path survey/outline.md --max-papers 140 --min-words 10000 --target-words 12000 --min-unique-citations 100 --target-unique-citations 110 --max-evidence-chars 150000 --bib-output survey/references.bib --output-path survey/native_survey_prompt.json`
   - This always uses the deterministic balanced selector over `paper_pool.jsonl`; use the same cap and citation targets for every retrieval profile and inspect the emitted `evidence_selection` manifest.
4. Run one native long-form writing stage:
   - `spawn_agent` survey-section-writer with `survey/native_survey_prompt.json`, then `wait_agent` → `survey/survey.tex`
5. Validate the frozen Survey word/section contract, standalone TeX, at least 100 distinct keys from `survey/references.bib`, and canonical identity; allow one bounded repair using only the frozen library when any gate fails.
6. Generate the related-work prompt from `survey/survey.json` and the completed TeX body:
   - `prepare-related-works-data --topic "..." --survey-path survey/survey.json --output-path related_works/rw_prompt.json`
   - The handoff includes the bounded full survey body and a relation brief from all sections. Do not truncate it to the opening context or require every mapped key; audit distinct, claim-bound citation coverage instead.
7. Run related-work synthesis:
   - `spawn_agent` survey-related-works with `related_works/rw_prompt.json`, then `wait_agent` → `related_works/related_works.tex`
8. Enforce both Survey and Related Works word/section contracts, package layout, citation consistency, canonical identity, and real compilation. A failed frozen gate permits one bounded same-library repair before the final failure is recorded:
   - `finalize-package --topic "..." --survey-root survey --related-root related_works --json`
   - `validate --workspace . --survey-root survey --tex survey/survey.tex --tex related_works/related_works.tex --bib survey/references.bib --json`
   - `python "$REASFLOW_PRIVATE_SKILLS_ROOT/survey/survey-tex-bib-packaging/scripts/build_publication.py" --workspace .`
   - `finalize-package` removes prompt/stage/library intermediates by default so the final workspace looks like an AutoSurvey delivery. Use `--keep-intermediates` only for debugging failed runs.

Required final files:
- `survey/survey.tex`
- `survey/survey.pdf`
- `survey/survey.json`
- `survey/references.bib`
- `related_works/related_works.tex`
- `related_works/related_works.pdf`
- `build/publication_report.json`

## Legacy Full Pipeline (fallback only)

Use the legacy multi-stage flow only to recover content when native TeX generation fails. Convert and validate its result into the TeX-only final contract; never deliver the Markdown intermediates.

# Phase 1: Outline Generation
1. `autosurvey_tools.py prepare-outline-data` → survey/stage1.json
2. For each prompt: `spawn_agent` survey-outline, then `wait_agent` → rough outlines
3. `autosurvey_tools.py merge-outline-data` → survey/stage2.json
4. `spawn_agent` survey-outline, then `wait_agent` → survey/section_outline.md
5. `autosurvey_tools.py prepare-subsection-outline-data` → survey/stage3.json
6. For each prompt: `spawn_agent` survey-outline, then `wait_agent` → subsection outlines
7. `autosurvey_tools.py merge-outline` → survey/merged_outline.md
8. `autosurvey_tools.py prepare-edit-outline-data` → survey/stage4.json
9. `spawn_agent` survey-outline, then `wait_agent` → survey/outline.md

# Phase 2: Survey Writing
10. `autosurvey_tools.py prepare-subsection-data` → survey/stage5.json
11. For each section: `spawn_agent` survey-section-writer, then `wait_agent`
12. For each section: citation-check prompts → `spawn_agent` survey-section-writer, then `wait_agent`
13. `autosurvey_tools.py assemble-survey` → survey/survey_raw.md
14. `autosurvey_tools.py resolve-references` → survey/survey.json

# Phase 3: LCE Refinement (two-pass even/odd)
15. `autosurvey_tools.py prepare-lce-data` (even) → survey/lce_even.json
16. For even-indexed subsections: `spawn_agent` survey-section-writer, then `wait_agent`
17. `autosurvey_tools.py prepare-lce-data` (odd, updated content) → survey/lce_odd.json
18. For odd-indexed subsections: `spawn_agent` survey-section-writer, then `wait_agent`
19. `autosurvey_tools.py assemble-survey` → survey/survey_refined.md
20. `autosurvey_tools.py resolve-references` → survey/survey.json (final)

# Phase 4: Related Works
21. `autosurvey_tools.py prepare-related-works-data` → related_works/rw_prompt.json
22. `spawn_agent` survey-related-works, then `wait_agent` → related_works/related_works_raw.tex
23. Reuse `survey/references.bib`; do not generate a second related-work bibliography.
24. Sanitize related_works_raw.tex → related_works/related_works.tex

# Phase 5: Judging
25. `autosurvey_tools.py prepare-judge-data` → survey/judge.json
26. For each criterion: `spawn_agent` survey-judge, then `wait_agent`

# Phase 6: Validation
27. `autosurvey_tools.py finalize-package` → enforce the TeX-only files, shared BibTeX consistency, and distinct-citation gates.
28. `autosurvey_tools.py validate` → consistency report

## Deliverables
- `survey/outline.md`
- `survey/survey.tex` + `survey/survey.pdf` + `survey/survey.json`
- `survey/references.bib` (synced copy for survey-mode evaluation)
- `related_works/related_works.tex`
- `related_works/related_works.pdf`
- `build/publication_report.json` with cite/BibTeX, compilation, and coverage gates
