---
name: experiment-design
description: Use when defining hypotheses, baselines, metrics, ablations, and evaluation protocols for an experiment plan
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

# Experiment Design

## Overview
Design experiments to answer a narrow question. Every run should test a hypothesis, not just generate more numbers.

## Checklist
1. State the hypothesis and falsification condition.
2. Choose baselines, metrics, and evaluation splits.
3. Reserve ablations for the claims that matter most.
4. Define logging requirements and stopping criteria.
5. Read `Alg_Exp/evidence/experiment_evidence.json` when present. Trace paper-derived datasets, partitions, baselines, metrics, and parameter ranges to their source.
6. Apply a task-relevance gate before reuse. Compare each paper's task, mechanism,
   privacy/threat model, and experiment objective with the current workspace.
   Reject mismatched papers instead of forcing them into the protocol.
7. Keep paper `reported_findings` separate from locally executed results. Preserve missing fields as evidence gaps and resolve warnings before execution.
8. Write `Alg_Exp/document/execution_contract.json`. It is the machine-readable boundary between a plausible plan and an executable experiment.
9. Validate the contract in planning mode. Before running any experiment, validate again with `--require-ready`.

## Execution Contract

The contract must contain:

- `status`: `ready` or `blocked`;
- `evidence_relevance`: accepted paper keys and rejected papers with reasons;
- `algorithm`: implementation path and SHA-256, entrypoint, state variables,
  exact update rules, proximal/projection rule, and privacy sensitivity/noise/accounting;
- `experiment`: datasets, baselines, metric computations, seeds, equal-budget
  rule, and exact commands;
- `unresolved_blockers`: empty only when `status=ready`.

Every paper-derived update, dataset, baseline, or metric uses
`"source": "paper"` and includes both `paper_key` and `evidence_location`.
The `paper_key` must appear in `evidence_relevance.accepted_paper_keys` or the
validator rejects the contract. Locally chosen values use `local_choice`; do not
disguise them as paper defaults.

Validate:

```bash
CONTRACT_VALIDATOR="$REASFLOW_PRIVATE_SKILLS_ROOT/experiment/experiment-design/scripts/validate-execution-contract.py"

# Planning may intentionally produce status=blocked.
python3 "$CONTRACT_VALIDATOR" --workspace .

# Mandatory immediately before any experiment command.
python3 "$CONTRACT_VALIDATOR" --workspace . --require-ready
```

If the algorithm contains `NotImplementedError`, a placeholder, a changed file
hash, unresolved update equations, or missing privacy calibration, the contract
remains `blocked` and no experiment is run.

## Deliverables
- experiment plan with hypotheses and metrics
- baseline and ablation table
- required artifacts for reproducibility
- source table for every paper-derived protocol choice
- validated `Alg_Exp/document/execution_contract.json`
