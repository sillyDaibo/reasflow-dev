# Independent adapter fidelity review

Approved after revision as a blocked partial invocation. Only initial X and genuine Riemannian gradient are comparable; unsupported metric/inner-solver trajectory is isolated as diagnostics.

Inspected manpqn/algorithms.py solve, objectives.cm_objective/Objective, subproblem.solve_tangent_subproblem and manifold projections/retraction. Native bdiag begins at objective Lipschitz; delta=1/t0 and Armijo fraction=1e-4 are hardcoded. Only bdiag is stored, not a dense B matrix; conditional beta has no undamped sentinel. The finite projected proximal inner solve, damping and stopping are retained. The cm_objective optional Lipschitz scalar does not independently expose requested B0, later delta, full-B recursion or exact inner solver.

Public objective normalization is preserved by H=Q/2 (Codex) or h=-Q/2 (ReasFlow). Original CM nonsmooth value and l1 prox remain unchanged; the nonzero linear c term is added only to smooth value/gradient. This is public problem-input extension, not a replacement algorithm mechanism.

Initial X0 enters original API. Codex performs its native initial polar retraction; ReasFlow copies X0. Only step1 X_before and Riemannian gradient precede unsupported tuning/inner updates and remain in standard observations. All 34 other requested items per case are missing; actual source-tuned states stay in diagnostics and cannot be treated as requested-experiment outputs.

Public exact subproblem, fixed delta/B0 and full-B/damping observations cannot be faithfully forced through these sources without replacing core update/inner solve. No full B matrix, damping sentinel, tangent norm or exact tangent solution is reconstructed from paper formulas. Approval is adaptation fidelity, not coverage or numeric algorithm correctness.

Readonly smoke on revised bytes exited 0 for both cases, with two standard observations per case and blocked status.

Substitutions inspected:
- CM quadratic data and linear c: Retains original CM quadratic/penalty/prox, adding public linear smooth term only when needed.
- sys.settrace: Reads native states and accepted line-search locals; unsupported-parameter trajectory goes exclusively to diagnostics.
- initial Riemannian gradient: ReasFlow uses native projected grad local; Codex applies original project_tangent to native Euclidean gradient at actual X without influencing updates.

Reviewed actual source functions and public inputs, not just author notes. Public-only readonly smoke exited 0 for both cases; stdout/stderr are in adapter-review-b-smoke/. No numeric private answer comparison or entire Judge invocation occurred. Approval concerns adaptation fidelity only; every reported block remains a coverage limitation. Digests were generated from current actual bytes and validate_adapter_review succeeded.
