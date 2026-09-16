# Independent adapter fidelity review

Approved as faithful partial execution with explicit blocked observations. Original IRLS routine and measurement operator are retained; absent spectral/operator states are not reconstructed.

Source simirls/algorithms.py:47 _initial_ls produces the identity-weight constrained minimum-norm initialization; :57 irls_lrrs computes norms/SVD/epsilon/delta and row_w before spectral_grad. Adapter trace at that line captures the post-solve/reweight state, beginning at step 1. Source then uses one-sided spectral_grad, rank/row thresholds and three refinements, not two-sided factors or a fixed W matrix. Adapter neither repairs these equations nor invents absent factors.

Public rank=1, sparsity=1, measurement matrix/y and iteration cap are native arguments. No smoothing floors, tolerance, inner steps, source weights or update equations are patched. Three traced post-solve states precede an unused final outer solve; step numbering is consistent with initialization being the first identity-weight solve.

Codex smoke emits 18 observations per case; ReasFlow emits 24 per case. All cases remain blocked for missing native spectral factors and/or weight_operator. This is not a correctness approval for the source IRLS variant.

Substitutions inspected:
- MeasurementOperator: Public sensing matrix and measurements enter original operator; Codex columns permuted from C vectorization to native F order, ReasFlow uses native C order.
- sys.settrace: Copies actual post-solve/reweight locals and first real weight-helper factors without changing state or generating a missing operator.

Reviewed actual source functions and public inputs, not just author notes. Public-only readonly smoke exited 0 for both cases; stdout/stderr are in adapter-review-b-smoke/. No numeric private answer comparison or entire Judge invocation occurred. Approval concerns adaptation fidelity only; every reported block remains a coverage limitation. Digests were generated from current actual bytes and validate_adapter_review succeeded.
