# 2501.09516 / codex
Read only permitted public material and original workspace source.

Calls `src/manpqn/algorithms.py:manpqn -> run_method` and its native tangent solver, prox, quasi-Newton update and SVD retraction. Native CM objective represents the quadratic exactly via H=Q/2. For quadratic_l1 the original objective is used unchanged. For indefinite_l1 only c^T X is added to the original smooth value and c to its smooth gradient; original nonsmooth penalty, prox and Lipschitz policy remain unchanged. No replacement l1 proximal operator is written.

Public X0, three-iteration cap, nonmonotone window and SVD selection are supplied through API. The source default inner budget (100), tolerance, float64, spectral Lipschitz initialization, stopping, curvature and line search are preserved. Public exact-inner-solve specialization cannot be imposed without replacing the algorithm's inner solver. The public caveat means mismatch with that specialization is not a general ManPQN algorithm-error claim.

Read-only trace observes pre-direction X, native gradient/metric, and accepted v/alpha/X/objective/reference/backtracks. The displayed metric_diagonal is explicitly the source inverse-like metric scaling, not a reconstructed Hessian. Riemannian gradient is a read-only call of the original project_tangent on the original Euclidean grad; it never changes the solver input. The source has no native weighted norm so that field stays missing.

The native ManPQN stores an inverse-like diagonal secant-ratio scaling, not a full damped BFGS B_matrix or damping_beta, and does not evaluate tangent_metric_norm_squared. The native approximate tangent solve and stopping were preserved; no exact solver substituted.

The requested fixed delta, identity initialization and exact solver are not patched into source internals. Missing core states remain blocked and are not computed from secant formulas, inferred damping or surrogate matrices. No sys.setprofile override; source immutable.


Independent-review scope correction: only initial observations independent of the unsupported public parameter survive in observations: [(1, 'X_before'), (1, 'riemannian_gradient')]. All later genuinely observed native-source states are retained under diagnostics.native_observations, and their required public fields are marked missing. Native trajectory is neither deleted nor presented as a realization of unsupported z0/B0/delta/exact-inner settings. This is an interface/coverage block, not a numeric correctness verdict.
