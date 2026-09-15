# Implementation review — 2026-09-15

Reviewer: `adapter_audit_controls`. This was a source review of the requested pipeline, review-record validators, assessment, wrapper and CLI files. Only newly constructed synthetic canaries were executed. No benchmark private contracts, private answers, derivations or historical verdicts were read. Production code was not edited by this reviewer.

## Findings and repair verification

1. **[P1, fixed and independently retested] Repository grep could read external symlink targets.** `execution._inspect(..., "grep", ...)` originally validated only the search root, then directly read every enumerated file. A link inside the workspace to an external synthetic private canary was rejected by `read_file` but exposed by `grep(path=".", pattern="PRIVATE_BOUNDARY_CANARY")`. That inspection function serves the new adapter-preparation, adapter-review and environment stages, so this violated their declared information boundary. The revised per-file `_rooted` check now returns `(no matches)` for the same canary. The pipeline also rejects external/cyclic workspace links before repository model inspection. The snapshot now records symlink text; internal target files remain covered by their own normal entries.

2. **[P1, fixed and independently retested] Execution could use an adapter different from the reviewed version.** The review was verified before environment setup, but neither the execution adapter nor the frozen adapter/public-input/bindings artifacts were checked afterward. The standalone synthetic reproduction added a comment to the runtime adapter and frozen adapter during setup; before repair it produced `PROBE_PASS`, `eligible_on_tested_scope`, and `executed_adapter_matches_review=false`, with source integrity true. The revised artifact hash checks reject that same reproduction before execution with `RUN_FAILED / EXECUTION_ARTIFACT_CHANGED / hold`. Public inputs and bindings are now included in the protected artifact set. Reproduction: `python3 reports/judge-hardening-cpu30-20260915/implementation_review_repro.py`.

3. **[P2, fixed and independently retested] Unknown case status is silently treated as success.** The pipeline strips every `status` field before numerical validation and recognizes only the exact string `blocked` afterward. A synthetic adapter declaring `status="unsupported"` with complete numerically correct observations was accepted as `PROBE_PASS / eligible_on_tested_scope`. This loses an interface-failure declaration and accepts an undeclared protocol state. The revised validator accepts only absent/`ok`/`pass`/`blocked` states and rejects other values as protocol metadata errors while preserving the numerical checks. The same canary now produces `RUN_FAILED / INVALID_OBSERVATION_METADATA / hold`. `pass` remains only a recognized declaration and cannot override numerical comparison. Reproduction: `python3 reports/judge-hardening-cpu30-20260915/implementation_review_repro.py --unknown-status`.

4. **[P2 robustness, fixed and independently retested] Artifact hash read errors can escape finalization.** The new artifact loop checks `is_file()` and then calls `_sha256_file()` without catching `OSError`. A permission/read race can throw in the pre-execution check; the outer exception handler invokes `finish`, whose identical unguarded read can throw again, leaving no final machine-readable assessment. The revised shared `artifacts_intact()` catches `OSError`. An additional synthetic fault-injection canary now forces this exact read error during finalization and still produces a structured `RUN_FAILED / EXECUTION_ARTIFACT_CHANGED / hold` result. This checks error handling without claiming a real filesystem-race reproduction. Reproduction: `python3 reports/judge-hardening-cpu30-20260915/implementation_review_repro.py --unreadable-artifact`.

## Additional review conclusions

- Missing paper or adapter approval cannot grant acceptance: numerical `PROBE_PASS` alone leaves `assessment.acceptance="hold"`, and the execution CLI returns success only for `eligible_on_tested_scope`.
- Supplied paper approval is bound to the complete validated contract digest, which includes original-paper SHA256 and private expectations. Every case must be covered exactly once; an overall approval requires every case approved.
- Adapter approval is bound to public JSON, adapter bytes, normalized bindings and workspace snapshot. Its declared substitution inventory rejects any approved `algorithm_replacement` entry. This validates record applicability and consistency, not the honesty or provenance of an external reviewer.
- The generated paper review is a distinct model call with no repository tools. Adapter review starts a distinct source-inspection conversation and receives public cases and adapter code, not the private contract. The repaired inspection boundary is material to that guarantee.
- Coverage and numeric evidence remain separate from acceptance, and the small-difference diagnostic does not enlarge frozen tolerances or waive mismatches.
- The wrapper forwards both review paths to the pipeline; the preparation CLI writes a digest-bound paper review and returns nonzero for rejection. No additional issue was found in those forwarding/exit paths.
- Runtime source-call tracing is provenance evidence, not an adversarial sandbox or a proof that every emitted number derives from a traced call. This remains a stated architectural limit; no hostile-code-sandbox claim was inferred.

## Verification limits

The canaries use a local integer-addition function and explicit synthetic zero/one observations, independent of all CPU30 paper experiments. These checks establish the reproduced control-flow defects and the repairs described above; they do not establish whole-pipeline security, mathematical contract validity, or benchmark correctness. Root-agent tests and CPU30 execution remain separate evidence.

## Final disposition

All four findings above were repaired by the root agent and independently retested here. No additional acceptance-bypass finding remains from this bounded review. This is a review of the recorded source versions, with the architectural and verification limits stated above.

- `repo_judge/src/judge/algorithm_pipeline.py`: `26f517d12cef6416720162bd3d6a1d739640a5e2fe50a0ad10b7b649ed13c99e`
- `repo_judge/src/judge/review_records.py`: `c9592168089c7392e08af71c248836188b8be9245ad56880a1d0e923eef3e0ad`
- `repo_judge/src/judge/algorithm_assessment.py`: `fcbda293a9fcdbd3c1c0907b8d5953904ba8793fcdf1f530d4694c93fabb9a54`
- `repo_judge/src/judge/execution.py`: `96c9faa598bf3e6c2b1a980e72b3c12b52477a7bc376b0f4f604ed2e76aab74c`
- `repo_judge/run_execution_judge.py`: `089022ea573c4fb210b99297d2014f0b3a667117373986c27a5c094f1ce99091`
- `repo_judge/prepare_algorithm_judge.py`: `df28102049c636c22dc4f28f0ce2e9c0919f3586cc5f4deda0e8b8585b682a29`
