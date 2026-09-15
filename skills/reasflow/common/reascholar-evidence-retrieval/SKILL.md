---
name: reascholar-evidence-retrieval
description: Retrieve traceable, paper-grounded algorithm or experiment evidence from ReaScholar and save compact workspace evidence packs plus raw API responses. Use before Algorithm designs or implements a method, before Experiment chooses datasets, baselines, metrics, parameters, or reproduction code, or whenever Alg_Exp plans need current paper evidence beyond local knowledge cards.
---

# ReaScholar Evidence Retrieval

Use ReaScholar as a paper evidence source, not as an authority that overrides the paper. Preserve raw responses and review warnings before using extracted content.

## Setup

Resolve the private skill root:

```bash
if [ -d ./.codex/reasflow-skills ]; then
  REASFLOW_PRIVATE_SKILLS_ROOT="$(pwd)/.codex/reasflow-skills"
elif [ -d "$HOME/.codex/reasflow-skills" ]; then
  REASFLOW_PRIVATE_SKILLS_ROOT="$HOME/.codex/reasflow-skills"
else
  echo "reasflow private skills not found" >&2
  exit 1
fi

EVIDENCE_ROOT="$REASFLOW_PRIVATE_SKILLS_ROOT/common/reascholar-evidence-retrieval"
```

## Algorithm evidence

Run one query for the proposed method family and problem, and another when a distinct mechanism materially affects the design:

```bash
python3 "$EVIDENCE_ROOT/scripts/retrieve-evidence.py" algorithm \
  --workspace . \
  --query "<algorithm family> <problem type> <key mechanism>" \
  --top-k 5 \
  --detail-top-k 3 \
  --output Alg_Exp/evidence/algorithm_evidence.json
```

The command searches algorithm-bearing papers, fetches structured details for the strongest paper results, includes proof cards, and performs a separate theorem search unless `--no-theorem-search` is passed.

Read `algorithm_evidence.json` and the referenced files under `Alg_Exp/evidence/raw/`. Use:

- `problem` for task, objectives, assumptions, and constraints;
- `method` for variants, initialization, update rules, design choices, and implementation notes;
- `theory` for statements and dependency edges;
- `code_snippets` only as implementation references.

Never execute returned code directly. Inspect the repository, license, file path, and surrounding code before porting an idea into `Alg_Exp/code/`.

## Experiment evidence

Search with the algorithm family, task, and dataset or topology:

```bash
python3 "$EVIDENCE_ROOT/scripts/retrieve-evidence.py" experiment \
  --workspace . \
  --query "<algorithm family> <task> <dataset or topology>" \
  --top-k 5 \
  --detail-top-k 3 \
  --output Alg_Exp/evidence/experiment_evidence.json
```

Add `--require-code` only when reproduction specifically requires a public implementation. Read:

- `datasets` for candidate data and partition rules;
- `baselines` for comparisons;
- `setup` for reported environment and parameters;
- `evaluations` for goals, metrics, settings, and paper-reported findings;
- `limitations` for missing coverage and additional tests;
- `code_snippets` for configuration and implementation references.

Treat `reported_findings` as results reported by a paper. Never copy them into the local-results section of an experiment report.

Before searching, read `Alg_Exp/evidence/algorithm_evidence.json` when it exists.
Use the Experiment query to fill missing protocol details rather than repeating
the Algorithm query. Paper-detail responses under `Alg_Exp/evidence/raw/` are
shared automatically: Experiment reuses a fresh Algorithm response for the same
paper instead of downloading it again.

## Evidence contract

Every run writes:

- the compact evidence pack requested with `--output`;
- the search and paper-detail responses under `Alg_Exp/evidence/raw/`;
- an append-only run list in `Alg_Exp/evidence/retrieval_manifest.json`.

The default cache window is 168 hours. Every evidence pack records search,
detail, and theorem cache hits plus SHA-256 hashes for raw responses. Use
`--refresh-cache` only when current evidence is required; use
`--cache-max-age-hours 0` to disable reuse for a controlled evaluation.

Inspect each paper's `warnings` before using it. An empty list or `null` means ReaScholar did not extract that information; do not fill it from memory. Resolve conflicts against the paper Markdown or canonical arXiv/DOI source.

Use local knowledge cards and ReaScholar together:

- local cards provide stable, reviewed conventions;
- ReaScholar provides paper-specific algorithms, experiments, theory, and code locations;
- the Algorithm or Experiment plan records which source supports each decision and which choices are new.

If ReaScholar is unavailable, keep the generated error evidence file. Continue only when local sources are sufficient for the user's request; otherwise report the evidence gap.
