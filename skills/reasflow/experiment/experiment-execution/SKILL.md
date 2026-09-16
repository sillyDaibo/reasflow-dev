---
name: experiment-execution
description: Use when running algorithm or experiment commands that need reproducible logs, workspace bootstrap, and long-run script generation
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

# Experiment Execution

## Overview
This skill replaces the most important parts of the upstream terminal and workspace helpers with concrete commands the Codex agent can run.
Use it whenever Algorithm or Experiment needs to prepare `Alg_Exp/`, create a workspace-local virtual environment, capture logs, or turn a long run into a reusable shell script.

## Workspace Bootstrap
Set `SKILL_ROOT="$REASFLOW_PRIVATE_SKILLS_ROOT/experiment/experiment-execution"`.
Then prepare the shared workspace with:

```bash
bash "$SKILL_ROOT/scripts/bootstrap-alg-exp.sh" "$PWD" Alg_Exp
```

This creates:
- `Alg_Exp/code/`
- `Alg_Exp/data/`
- `Alg_Exp/document/`
- `Alg_Exp/picture/`
- `Alg_Exp/logs/`
- `Alg_Exp/cache/`
- `Alg_Exp/temp/`
- `Alg_Exp/latex/`
- `Alg_Exp/scripts/`
- `Alg_Exp/.venv/`

If Python environment creation fails, use `uv` explicitly:

```bash
uv venv Alg_Exp/.venv
Alg_Exp/.venv/bin/pip install numpy scipy matplotlib pandas scikit-learn optuna pypdf
```

## Logged Execution
For short or medium runs that should execute now, capture a timestamped log with:

```bash
python3 "$REASFLOW_PRIVATE_SKILLS_ROOT/experiment/experiment-design/scripts/validate-execution-contract.py" \
  --workspace . --require-ready

bash "$SKILL_ROOT/scripts/run-with-log.sh" Alg_Exp/logs \
  Alg_Exp/.venv/bin/python Alg_Exp/code/test_algorithm.py
```

The validation command is a hard gate. Do not run the following command when it
fails or when the contract status is `blocked`.

Always record the exact command, output path, and whether the run passed.

## Self-Recovery Retries
When a run fails, capture `stderr` and the exception traceback and feed them
back into the next attempt so the agent can fix its own script. Retry up to a
configurable limit (default `3`, overridable in the plan). If consecutive
failures hit the limit, fall back to a last-known-good configuration (the
configuration of the most recent run that passed the reproducibility gate, or
the most recent run that completed successfully) or record
the partial results and continue; do not stop and wait for a human.

## Budgets and Early Stopping
Every experiment honors the `budget` field from the contract: a wall-clock
cap and an iteration cap per run. Stop a run early when either cap is reached
and preserve its partial results under `Alg_Exp/logs/` and `Alg_Exp/data/`.
When the global budget (the sum of all per-run budgets) is exhausted, converge
the conclusion on the results already collected rather than launching new runs.

## Long-Running Commands
When a command is too long or expensive to run inline, generate reusable platform scripts first:

```bash
python "$SKILL_ROOT/scripts/prepare-long-run.py" \
  --workspace "$PWD" \
  --output-root Alg_Exp \
  --command "python Alg_Exp/code/experiment.py --epochs 500 --seeds 1 2 3" \
  --script-name main_experiment
```

The helper writes both:
- `Alg_Exp/scripts/main_experiment.sh`
- `Alg_Exp/scripts/main_experiment.bat`

It also prints JSON containing:
- estimated runtime
- POSIX command
- Windows command
- detected virtual environment path

## Dataset Staging
When Experiment needs to copy or download a dataset into the shared workspace, use:

```bash
python "$SKILL_ROOT/scripts/stage-dataset.py" \
  --source https://example.com/dataset.zip \
  --output-dir Alg_Exp/data/raw \
  --extract
```

The same helper also accepts local paths:

```bash
python "$SKILL_ROOT/scripts/stage-dataset.py" \
  --source ./downloads/my_dataset \
  --output-dir Alg_Exp/data/raw
```

## Execution Contract
1. Require a valid, ready `Alg_Exp/document/execution_contract.json`.
2. Bootstrap `Alg_Exp/` before the first serious run if the workspace is not already prepared.
3. Use the workspace-local `.venv` instead of system Python whenever possible.
4. For every important run, keep a stable log file under `Alg_Exp/logs/`.
5. For long jobs, generate scripts before handoff so the user or a later agent can rerun exactly the same command.
6. Stage downloaded or copied datasets under `Alg_Exp/data/raw/` unless the workspace already uses a stricter convention.
7. Put result files under `Alg_Exp/data/`, `Alg_Exp/picture/`, or `Alg_Exp/document/` instead of ad hoc locations.

## Reproducibility Gate
Before declaring a run delivered, verify:

- random seeds are fixed and recorded for every stochastic component;
- the environment is captured (dependency versions, hardware) so the run can
  be replayed;
- hyperparameters are logged alongside the result, not just in the script;
- single-variable control is respected: each run changes exactly one
  independent variable against a shared baseline.

This gate complements the contract's evidence gate; a run that fails it is
treated as partial, not delivered.

## Deliverables
- executed command ledger with log paths
- generated run scripts for long jobs when needed
- note on missing dependencies or environment issues
