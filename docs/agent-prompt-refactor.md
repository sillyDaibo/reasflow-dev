# Algorithm and Experiment Prompt Refactor

Date: 2026-08-03

## Goal

Reduce brittle, rule-heavy Agent prompts without weakening evidence quality,
execution safety, or reproducibility. Detailed procedures belong in Skills and
machine validators; Agent prompts should define the mission, current stage,
decision principles, hard boundaries, deliverables, and completion criteria.

## Official guidance used

- [OpenAI GPT-5.6 prompt guidance](https://developers.openai.com/api/docs/guides/prompt-guidance-gpt-5p6.md):
  prefer shorter outcome-oriented prompts, explicit success criteria,
  dependencies, stopping conditions, autonomy boundaries, tool routing, and
  real validation. Make the smallest prompt change needed for a measured
  failure and evaluate representative traces.
- [Anthropic: Effective context engineering for AI agents](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents):
  use the smallest high-signal context that fully specifies expected behavior;
  avoid brittle hard-coded if/else logic and vague high-level guidance; retrieve
  detailed context just in time; use canonical examples instead of a laundry
  list of edge cases.
- [Anthropic: Demystifying evals for AI agents](https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents):
  evaluate the final state and artifacts rather than a prescribed action path;
  combine deterministic and model-based graders; use isolated environments,
  balanced tasks, reference solutions, repeated trials, and transcript review.
- [Anthropic prompt engineering best practices](https://platform.claude.com/docs/zh-CN/build-with-claude/prompt-engineering/claude-prompting-best-practices):
  use clear, direct instructions and relevant context; prefer general guidance
  over manually prescribing every reasoning step.

These sources do not say that every constraint should be removed. Evidence
provenance, permission boundaries, irreversible-action controls, output
contracts, and execution gates remain explicit because they define correctness
and safety.

## Problems in the previous prompts

The previous Agent prompts repeated material already owned by enabled Skills:

- shell commands for knowledge cards, ReaScholar, tuning, plotting, and virtual
  environments;
- code, report, and LaTeX templates;
- separate validation, comparison, tuning, plotting, and error-handling
  scenarios;
- multiple overlapping rules for when to ask, stop, continue, or rerun;
- contradictory environment guidance between Algorithm and Experiment.

This increased maintenance cost and context load. A Skill change could leave a
stale copy in the Agent prompt, and fixed call counts could cause retrieval even
when no unresolved design question remained.

## Refactor

Both prompts now use the same high-level shape:

1. host and leaf-agent boundary;
2. role and shared workspace;
3. current stage: planning or approved execution;
4. outcome-oriented working method;
5. evidence and execution boundaries;
6. concrete deliverables;
7. completion standard.

Detailed commands and templates remain in the enabled Skills. ReaScholar
retrieval is driven by unresolved evidence gaps rather than a fixed number of
queries. Experiment execution still requires the machine-readable ready
contract. Missing evidence, placeholder code, stale hashes, unsupported papers,
and incomplete privacy definitions remain blockers.

## Static prompt comparison

| Agent | Metric | Before | Candidate | Change |
|---|---|---:|---:|---:|
| Algorithm | characters | 13,422 | 5,583 | -58.4% |
| Algorithm | lines | 314 | 115 | -63.4% |
| Algorithm | rule-like markers | 51 | 18 | -64.7% |
| Experiment | characters | 18,940 | 6,382 | -66.3% |
| Experiment | lines | 442 | 125 | -71.7% |
| Experiment | rule-like markers | 63 | 15 | -76.2% |

`tests/test_agent_prompt_contract.py` protects the reduced context budget and
the outcome contracts that must remain.

## Before/after evaluation protocol

The behavioral evaluation changes only the two Agent prompts:

- **baseline**: the ReaScholar-enabled source at commit `1e9f5e7` with the
  previous prompts;
- **candidate**: the same source and ReaScholar/contract scripts with the
  refactored prompts.

Both arms use the same Codex binary, model, task text, ReaScholar access,
network allowlist, clean workspace, timeout, and hidden paper reference. The
task order and A/B display order are seeded and hidden from judges.

The initial paired suite covers all six research tasks for Algorithm planning
and Experiment planning. It uses:

- deterministic checks for completion, topic coverage, evidence retrieval,
  hidden-reference-paper hit, raw provenance, source tables, relevance records,
  and execution-contract validity;
- blind pairwise grading of correctness, reference fidelity, feasibility,
  provenance/uncertainty, and clarity;
- duration and trajectory review to detect redundant retrieval, tool loops,
  contamination, and timeouts.

The candidate is considered a safe prompt simplification only when:

- completion and hard-gate pass rates do not decrease;
- no new unsupported execution or fabricated-result behavior appears;
- the paired quality score does not show a practically meaningful regression
  (provisional non-inferiority margin: -1 point on the 20-point judge scale);
- any latency or token reduction is not purchased by lower evidence coverage.

One six-task replicate is a pilot for failure discovery, not a final
statistical claim. A release decision should use at least three replicates and
periodic human review of sampled trajectories.

## Evaluation results

The server-side pilot used six tasks, one replicate, and two blind judges
(`gpt-5.6-sol` and `gpt-5.6-terra`). The first full pass exposed two Algorithm
failures: the candidate replaced the paper-supported server-side
FedProx-SPIDER update in `private_fl`, and replaced total-budget threshold
selection with a fixed-per-round selector in `sparsification`. Experiment had
one task-level loss on `parq_quantization`.

A single general principle was added in response: use the strongest
task-matching paper as the evidence anchor, preserve its defining mechanism and
measurement semantics, and represent local changes as explicit deltas with an
anchor-aligned baseline or rollback. Experiment planning also gained a compact
evidence-relevance-table deliverable. Only the affected tasks and missing-table
cases were rerun; unchanged task outputs were retained. Composition manifests
in the final result directories record every replacement.

### Final quality and hard gates

| Stage | Blind result (candidate vs baseline) | Mean score delta / 20 | Bootstrap 95% CI | Candidate hard-gate result |
|---|---:|---:|---:|---|
| Algorithm | 5 wins / 1 tie / 0 losses | +2.67 | [+2.08, +3.33] | 6/6 valid, complete, evidence-backed, raw provenance valid, and source table present |
| Experiment | 4 wins / 2 ties / 0 losses | +3.92 | [+1.50, +5.75] | 6/6 valid, complete, evidence-backed, contract-valid, and correctly blocked at the ready gate |

Algorithm hidden-reference-paper hit rate increased from 5/6 to 6/6.
Experiment increased from 4/6 to 5/6. The candidate separated paper-reported
claims from local execution in every Algorithm output; the baseline failed that
deterministic check in all six outputs.

These results pass the provisional -1/20 non-inferiority margin in this pilot.
They do not constitute a release-level statistical proof: there is one
replicate, the server and model gateway were shared, and the final aggregate
uses failure-driven replacement runs rather than a second full preregistered
suite.

### Runtime and token cost

| Stage | Metric | Baseline | Candidate | Direction |
|---|---|---:|---:|---|
| Algorithm | mean wall time | 508.5 s | 536.6 s | candidate +5.5% |
| Algorithm | mean input tokens | 1.338 M | 2.101 M | candidate +57.0% |
| Algorithm | mean non-cached input tokens | 96.8 K | 126.7 K | candidate +31.0% |
| Algorithm | mean output tokens | 22.1 K | 27.3 K | candidate +23.7% |
| Algorithm | mean completed commands | 23.8 | 28.0 | candidate +17.5% |
| Experiment | mean wall time | 344.4 s | 344.4 s | effectively equal |
| Experiment | mean input tokens | 819 K | 967 K | candidate +18.0% |
| Experiment | mean non-cached input tokens | 76.2 K | 88.4 K | candidate +16.1% |
| Experiment | mean output tokens | 19.5 K | 20.5 K | candidate +5.1% |
| Experiment | mean completed commands | 24.2 | 20.8 | candidate -13.8% |

The refactor reduces static prompt context and rule maintenance, but it does not
reduce total execution tokens in this pilot. Moving operational detail into
Skills led the agents to read more just-in-time context and raw evidence. The
quality gain is therefore real, while an efficiency gain is not established.

### Evaluation-harness corrections

The pilot also found and fixed three benchmark defects:

- direct-agent extraction had hard-coded one grammatical role phrase and
  rejected the equivalent candidate phrase before execution;
- the blind-judge subprocess did not catch its 300-second timeout;
- the source-table grader missed valid tables whose column was named
  `Evidence location`.

Regression tests now cover all three. Infrastructure-invalid starts and judge
timeouts were retained for audit but excluded from Agent-quality comparisons.

The final local result directories are:

- `/home/hzy/Eva-for-Alg-Exp/reascholar_ab_eval/results/prompt_refactor_algorithm_final_v3`;
- `/home/hzy/Eva-for-Alg-Exp/reascholar_ab_eval/results/prompt_refactor_experiment_final_v4`.

The final candidate source snapshot passed all 39 tests on the Linux evaluation
server. The macOS checkout passes 38/39; the remaining pre-existing failure is
the Intro citation test's `/var` versus `/private/var` workspace-path
normalization and is unrelated to these prompts.
