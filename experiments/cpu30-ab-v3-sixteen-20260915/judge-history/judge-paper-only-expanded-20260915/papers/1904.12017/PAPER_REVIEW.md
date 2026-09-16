# Paper-only review: 1904.12017

This private numerical contract was derived only from the original PDF, *A Distributed Method for Fitting Laplacian Regularized Stratified Models*, Jonathan Tuck, Shane Barratt, Stephen Boyd, November 12, 2019. No implementation, benchmark data, existing contract, result, run, or derived dataset card was consulted. The only project code read was `repo_judge/src/judge/paper_contract.py`, for its schema and validation interface. General arithmetic libraries are used only for independently computing and checking the paper's equations.

## Visually checked primary evidence

The original PDF pages 7, 15, 16, 36 and 37 were rendered with PyMuPDF and visually inspected, including complete equations and labels. Page numbers here are one-based PDF pages, matching printed page numbers.

- Page 16, Algorithm 4.1 specifies all-zero initialization and the two separate local proximal evaluations, graph consensus solve and two scaled-dual updates.
- Page 16, Eq. (5) specifies the consensus system `(L + 2/lambda I) H_new = (X_new + U_old + T_new + V_old)/lambda` independently for each parameter component.
- Page 15, Eq. (4) and the accompanying augmented Lagrangian explain the loss/regularizer/graph split and the proximal scale.
- Page 36, Appendix A defines proximal minimization and gives the quadratic shrinkage and soft-threshold functions used here.
- Page 37, Appendix A gives the general quadratic proximal formula and the Poisson negative-log-likelihood proximal formula.
- Page 7 defines the graph Laplacian. Every test supplies L directly in node order.

## Contract scope and public conventions

The subject is the entire four-part update of Algorithm 4.1, not a standalone proximal helper. Each of three experiments runs four complete iterations and observes all five mathematical states at iterations 1, 2 and 4: loss state `theta`, regularizer state `theta_tilde`, graph state `theta_hat`, and scaled dual states `u`, `u_tilde`. This produces 45 array observations / 225 scalar checks. The fourth iteration is the final fixed-budget result; these tests do not assert convergence in four iterations.

Every public case specifies inputs, proximal scale, dimension, initialization, iteration count, state names, timing and solver conventions. The public algorithm assumptions define node-major K by n arrays; generic quadratic losses `0.5*x.T@Q[k]@x + b[k].T@x`; Poisson sufficient statistics; the exact regularizer normalization; and the graph scaling. No answer or private derivation is needed to understand the public contract. All cases use lambda > 0, convex losses/regularizers and a connected valid weighted graph.

1. **correlated_quadratic_ridge:** Three strata, two parameters per stratum, non-diagonal positive definite local Hessians, unequal weighted triangle, lambda = 0.5 and ridge coefficient 0.75. It tests within-node parameter coupling together with graph coupling, avoiding a scalar-only graph helper case.
2. **empty_node_l1_path:** Three strata, two parameters, unequal path weights, lambda = 1 and l1 coefficient 0.2. The middle node has Q = 0 and b = 0, representing no local data. Graph propagation makes its consensus state nonzero. By iteration 2, the regularizer branch contains positive, negative and exactly zero outputs; by iteration 4 one middle-node coordinate crosses the threshold.
3. **poisson_ridge_graph:** Three scalar strata, Poisson counts [2, 1, 3], sums [4, 3, 2], unequal weighted triangle, lambda = 2 and ridge coefficient 0.5. Feasible underlying count records include [1, 3], [3], and [0, 1, 1]. This activates a nonlinear loss proximal operator inside the complete ADMM trajectory. All loss proximal states are strictly positive.

## Independent arithmetic and checks

`derive_contract.py` uses exact Fraction arithmetic and Gauss-Jordan elimination for the two quadratic experiments. For Poisson it uses Decimal arithmetic at precision 70 and the paper's square-root formula. It derives every intermediate state from all-zero initialization and does not embed expected trajectory constants.

A separate NumPy floating-point calculation solves the quadratic and graph first-order systems in differently scaled forms. Poisson minimizers are checked by bisection of the scalar first-order derivative, without using the square-root expression. Additional checks verify the local quadratic gradient, Poisson gradient, l1 subgradient/ridge gradient, positive-semidefinite quadratic Hessians, and the consensus KKT identity `u + u_tilde = lambda * L @ theta_hat` after every iteration. Maximum absolute discrepancy between independent calculations is 4.440892098500626e-16 for each experiment. Contract tolerances are atol = 1e-9 and rtol = 1e-8, allowing ordinary accurate floating-point solvers.

The contract passes `validate_contract` against the actual PDF SHA256. Its public projection was checked for complete observation coordinates and removal of private expected values and derivations. Re-running the derivation must produce the same contract bytes.

Private final graph-consensus states, useful for independently auditing this review:

- correlated_quadratic_ridge: `[[0.6875897777872474, -0.051059196737855965], [0.04367406417666921, 0.6726140144715365], [0.13211443502033368, 1.1109262781565874]]`
- empty_node_l1_path: `[[1.158398219611593, -0.26214259186530975], [0.024802305549863776, 0.19390186377296634], [-0.5257332908347183, 0.5710710718188649]]`
- poisson_ridge_graph: `[[1.249794624046086], [1.2522840609469112], [0.8565721484777161]]`

## Paper ambiguities resolved before implementation inspection

The following choices are explicit in the public assumptions; none was chosen by observing implementation behavior.

- Page 7's double-sum Eq. (2) and following half-quadratic expression disagree by a factor of two for the stated standard Laplacian. We test the explicitly stated Algorithm 4.1 / Eq. (5), supplying L directly and never inferring its scale from Eq. (2).
- Page 15's unsimplified consensus argmin contains old-iteration superscripts. The explicit system in Eq. (5) uses the newly computed loss and regularizer states; the contract follows Eq. (5).
- Page 37's least-squares example has a sign inconsistent with both its immediately preceding general quadratic formula and proximal minimization. Quadratic inputs use the general Q,b formula, whose sign also follows independently by differentiating the proximal objective.

The optional adaptive penalty rule, stopping thresholds, particular CG routine, parallel execution speed, statistical fitting quality and large-scale convergence are outside this finite-trajectory contract. Numerical agreement proves only the observed core algorithm behavior on these cases.

## Freeze

Paper SHA256: `c8df517a9d0fde3ae1359ce97c14513289590549b17364241ca857d2d755a811`.

Canonical validated contract digest (`contract_digest`, distinct from file-byte SHA256): `33d242b7451add6d831f5ded3f9a5a3e49579e31ed5a015ec5ec0f28339f8ecb`.

File-byte hashes are recorded in `SHA256SUMS`. These artifacts are frozen before any implementation is inspected and must not be revised to match implementation behavior.
