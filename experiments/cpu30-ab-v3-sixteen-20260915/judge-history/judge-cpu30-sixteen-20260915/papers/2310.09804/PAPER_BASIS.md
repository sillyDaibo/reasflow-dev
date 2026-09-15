# Paper basis: 2310.09804

Only the supplied paper PDF was used to define expected values. No reproduction code, adapters, outputs, historical assessments, or other reports were read. The source SHA256 is pinned in contract.json.

## Source and exact scope

PDF p.6, Algorithm 2 Byz-DASHA-PAGE, visually verified: line 6 updates the shared point with the **previous server** estimate; lines 7-11 either refresh the full gradient or accumulate a same-component gradient difference in `h_i`; line 12 compresses `h_i(next)-h_i-old - a*(g_i-old-h_i-old)`; line 13 accumulates the message into the **local** `g_i`; line 16 robustly aggregates complete local estimator states. The theorem on this page initializes `g_i^0` with the full local gradient. This fixture explicitly initializes `h_i^0` the same way.

PDF p.17, Appendix B.1 and Algorithm 5, visually verified: bucketing permutes inputs and averages consecutive buckets before applying an aggregator; coordinatewise median takes the median in each coordinate. The paper explains why bare conventional aggregation rules need robustification. The contract therefore uses actual size-two bucketing with six workers (three complete buckets), followed by the coordinatewise median, rather than leaving aggregation unspecified.

PDF p.18, Appendix B.2, Rand-K, visually verified: select a uniform subset and scale retained entries by `d/K`. The fixture uses dimension two, K=1, hence multiplier two and omega=1.

## Experiments and boundaries

Five honest workers hold heterogeneous strongly convex quadratics, with two finite-sum components each; a sixth worker supplies explicitly specified Byzantine estimator states. Each of the two cases completes three updates. One uses difference/difference/refresh, the other refresh/difference/difference. Compression coordinates and permutations are all public supported outcomes of the prescribed random laws. Gradients use the same sampled component at old and new points in difference steps. All timing and malicious-state versus increment semantics are public.

Both cases develop a nonzero discrepancy between `g_i` and `h_i`, so momentum correction and persistent local estimator memory affect later steps. Observations include shared points, PAGE estimators, compressor inputs/messages, local estimators, bucket means, server estimates, and honest-worker objective values.

Exact rational arithmetic, including `a=1/3`, derives all private values independently; JSON conversion happens once. The private derivation includes exact Fraction traces. `atol=rtol=1e-10` permits routine double precision roundoff over three steps. The decimal public momentum is accompanied by its exact rational interpretation.

This contract validates Algorithm 2 with one explicit permissible compressor/aggregation instantiation. It does not test the other proposed algorithms, convergence rates, allowable adversary-fraction constants, or theorem-specific step-size sufficiency. It is an authoring basis, not an independent paper review.
