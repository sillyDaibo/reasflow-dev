# Paper basis: 2207.04555

Read only the supplied paper PDF. The title and source SHA256 are recorded in contract.json. No reproduction code, adapters, observations, historical evaluation, or other reports were consulted.

## Exact scope and locations

- PDF p.4, Assumption 2 and problem (3): a connected graph is represented by a positive semidefinite gossip matrix with consensus kernel; stacked primal variables obey both `W x = 0` and `(I tensor B) x = 0`.
- PDF p.5, equation (4): `A = [I tensor B; gamma (W tensor I)]` couples primal and dual variables.
- PDF p.5, Algorithm 1, visually checked against rendered PDF: lines 5-7 define `y_m`, `x_g`, `y_g`; lines 8-9 update `x` then `y`; lines 10-11 update fast variables using differences from **old** `x` and `y`.

This paper discusses known methods applied to its constrained setting. The contract tests exactly its displayed APDG primal approach and does not invent a new optimizer. It does not test the separate dual methods or Chebyshev acceleration.

## Fixtures and checks

Two heterogeneous strongly convex, two-node/two-dimensional quadratics use nontrivial affine and consensus constraints. The second fixture changes constraint scaling, objective, and initialization. The initial primal vectors are in `Range A^T` because their second coordinates sum to zero; the dual vectors are explicitly generated as `A w0`. Algorithm input parameter domains hold. The chosen parameters are recurrence fixtures, without claims of theorem-optimal tuning or convergence-rate validation.

Each case completes three updates and records the extrapolates consumed by that update, all four updated main/fast states, the constraint residual, and the objective at the updated primal state. All calculations use exact rational arithmetic in the independent derivation script; JSON conversion happens only after the values are computed. Absolute and relative tolerances of `1e-10` accommodate ordinary binary64 evaluation of these short recursions while remaining far below meaningful state changes.

`derive_contract.py` has no repository implementation input. `public_cases.json` is created with the prescribed `public_contract` schema helper and contains observation names/shapes but no hidden values or derivation. This authoring note is not an independent paper review.
