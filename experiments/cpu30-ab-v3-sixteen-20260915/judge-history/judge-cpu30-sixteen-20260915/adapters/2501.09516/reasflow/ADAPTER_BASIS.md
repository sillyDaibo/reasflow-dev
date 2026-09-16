# 2501.09516 / reasflow
Read only permitted public material and original workspace source.

Calls `src/manpqn/algorithms.py:solve` and its native tangent solver, prox, quasi-Newton update and SVD retraction. Native CM objective represents the quadratic exactly via h=-Q/2. For quadratic_l1 the original objective is used unchanged. For indefinite_l1 only c^T X is added to the original smooth value and c to its smooth gradient; original nonsmooth penalty, prox and Lipschitz policy remain unchanged. No replacement l1 proximal operator is written.

Public X0, three-iteration cap, nonmonotone window and memory=1 are supplied through API. The source default inner budget (100), tolerance, float64, spectral Lipschitz initialization, stopping, curvature and line search are preserved. Public exact-inner-solve specialization cannot be imposed without replacing the algorithm's inner solver. The public caveat means mismatch with that specialization is not a general ManPQN algorithm-error claim.

Read-only trace observes pre-direction X, native gradient/metric, and accepted v/alpha/X/objective/reference/backtracks. quad is the native weighted tangent norm. The source stores only bdiag; it never forms dense B.

The native ManPQN stores bdiag only; no full B_matrix exists. beta is conditionally assigned after accepted steps and no beta state exists for undamped pairs, so damping_beta is not fabricated. Native approximate tangent solve, Lipschitz initialization, damping, Armijo fraction and stopping were preserved.

The requested fixed delta, identity initialization and exact solver are not patched into source internals. Missing core states remain blocked and are not computed from secant formulas, inferred damping or surrogate matrices. No sys.setprofile override; source immutable.


Independent-review scope correction: only initial observations independent of the unsupported public parameter survive in observations: [(1, 'X_before'), (1, 'riemannian_gradient')]. All later genuinely observed native-source states are retained under diagnostics.native_observations, and their required public fields are marked missing. Native trajectory is neither deleted nor presented as a realization of unsupported z0/B0/delta/exact-inner settings. This is an interface/coverage block, not a numeric correctness verdict.
