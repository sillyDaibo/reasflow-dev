# 2306.04961 / codex
Only ADAPTER_GUIDE, this paper's public cases, PUBLIC_TARGETS entry and original source were used.

Calls `simirls/algorithms.py:irls_lrrs` with the original MeasurementOperator, public matrix/measurements, rank/sparsity and iteration cap. Codex receives only a C-to-F column permutation to preserve its native F vectorization; ReasFlow uses native C order. No normalization, updates, weights, thresholds, line search, inner-step counts, default tolerance, floor or dtype is overridden.

The original least-squares initialization is the first constrained solve (public step 1). The first loop's pre-update X and the source-computed singular/row values, smoothing and weights are observed as step 1; each later loop records the preceding genuine update. Three outer iterations are invoked; the final outer update is outside the three requested post-solve/reweight states. Read-only `sys.settrace` captures source locals and does not modify them. A native early stop can leave later states missing.

Source forms one-sided spectral_grad and row_w, with rank/row thresholds and projected refinements; no two-sided low-rank factors or fixed weight_operator matrix are formed. Original weights and solver unchanged.

Only actual source locals are emitted. Missing states are explicitly blocked; available source values are not replaced with public-contract formulas. ReasFlow left/right/row weights are from its first real _weight_apply call for each frozen pre-solve state. No expected values or comparisons were used.

