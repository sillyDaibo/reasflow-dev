# Independent adapter fidelity review

Approved as faithful partial execution with explicit blocked observations. Original IRLS routine and measurement operator are retained; absent spectral/operator states are not reconstructed.

Source simirls/core.py:147 irls_lrrs projects zero to the measurement set, then computes SVD/row statistics and smoothing. Trace first inner-loop-header visit records the corresponding post-solve state once; first actual :117 _weight_apply invocation supplies genuine left/right/row_w locals for that state. Row weights are recomputed from each inner x, so the helper is nonlinear in its argument; no fixed linear weight_operator exists to observe. Active-rank and stopping behavior are preserved.

Public rank=1, sparsity=1, measurement matrix/y and iteration cap are native arguments. No smoothing floors, tolerance, inner steps, source weights or update equations are patched. Three traced post-solve states precede an unused final outer solve; step numbering is consistent with initialization being the first identity-weight solve.

Codex smoke emits 18 observations per case; ReasFlow emits 24 per case. All cases remain blocked for missing native spectral factors and/or weight_operator. This is not a correctness approval for the source IRLS variant.

Substitutions inspected:
- MeasurementOperator: Public sensing matrix and measurements enter original operator; Codex columns permuted from C vectorization to native F order, ReasFlow uses native C order.
- sys.settrace: Copies actual post-solve/reweight locals and first real weight-helper factors without changing state or generating a missing operator.

Reviewed actual source functions and public inputs, not just author notes. Public-only readonly smoke exited 0 for both cases; stdout/stderr are in adapter-review-b-smoke/. No numeric private answer comparison or entire Judge invocation occurred. Approval concerns adaptation fidelity only; every reported block remains a coverage limitation. Digests were generated from current actual bytes and validate_adapter_review succeeded.
