# 1904.12017 public-only ADMM adapter review

## Access boundary and actual execution

Only the public `public/1904.12017/public_cases.json` and the specified original workspace source modules were read for this adapter. No 1904.12017 private contract, hidden derivation, paper PDF, existing evaluation output or repository tests were read or used. The adapter does not contain expected trajectories, compare outputs, or synthesize missing states.

The single-file adapter reads `OPTIREPRO_CASES` and `OPTIREPRO_WORKSPACE`. Each public case calls the original complete ADMM function once with maxiter=4. Python `sys.settrace` only reads/copies frame locals at a source-identified point after both scaled dual updates; no source AST rewriting, monkeypatching of updates, state mutation by the trace function, or consensus reimplementation occurs. A namespace package and explicit module loading avoid unrelated wildcard package imports while executing the original source functions unchanged.

All five observations use node-major K by n matrices. Observation steps 1,2,4 are emitted in the public requested order. The trace captures states after full iteration updates, before stopping/adaptation checks. Adaptation is fixed for these calls; no arithmetic is performed on captured states except copying to a float NumPy array, checking shape/finiteness, and serializing its original values.

## Input adaptation

The public proximal scale lambda maps to the existing rho argument as rho=1/lambda. The supplied L is passed without rescaling. Both implementations initialize all five states to zero through their existing defaults. Full original iterations run with abs_tol=rel_tol=0; all three public cases actually reached four complete iterations. These zero tolerances do not promise that an arbitrary exactly converged future input could never stop early; any missing requested state would be emitted as blocked rather than fabricated.

For a public quadratic `0.5*x^T*Q*x+b^T*x`, the existing original sum-squares proximal is supplied sufficient statistics `XtX=Q/2`, `XtY=-b/2`. Its quadratic expansion is exactly the public objective up to an irrelevant constant; this conversion does not solve the ADMM subproblem in the adapter. The original proximal solver computes each actual local state. The zero-loss middle stratum is represented by zero statistics without special-case iteration logic.

Poisson callbacks pass the public counts and sums directly to the original Poisson proximal. Its original positivity floor of 1e-5 is retained, not adjusted to fit an oracle. Ridge callbacks apply the public coefficient to all coordinates with no unpenalized intercept. Shape, sufficient statistics and coefficient injection are the public problem-input boundary.

## Smoke and dependency record

Public-only smoke ran using `/tmp/optirepro-paper-judge-20260915/bin/python` with `PYTHONDONTWRITEBYTECODE=1`. All three cases returned 15 requested observations, giving 45 matrices and no blocked case. Exactly one `OPTIREPRO_OBSERVATIONS=` marker was emitted. `smoke.stdout` records actual execution output; it was checked only for protocol, shape, finiteness and completeness, never against private expected values.

Hashes of the original imported source files were taken before and after execution and remained identical (`source_sha256.json`). No original workspace or pipeline edits were performed. `environment_actions.json` lists all required external packages with original import locations, including already installed packages, so a clean replay environment can install them. NetworkX was the only missing package encountered and was installed only into the temporary venv.

## Scope limits

This adapter tests the exposed generic full ADMM routine with public synthetic problem inputs. It does not claim correctness of graph construction from arbitrary data, end-to-end model wrappers, objective setup utilities, random data processing, timing or asymptotic convergence. It preserves original precision and CG behavior. If the original source changes so the trace point is not uniquely found, or a state is nonfinite/missing, the adapter reports blocked with legitimate observations captured before the issue.

## Codex original bindings and trace timing

`strat_models/solvers.py::fit_admm` is the unmodified complete original iteration. `_solve_system` uses original sparse SciPy CG with rtol=1e-8, atol=0 and default max_cg_iterations=50. No solver or tolerance is replaced. The supplied sparse L is packaged through the original `GraphOperator` constructor, with its original class and CSR matrix branch intact.

Source line 82, immediately before `primal = np.linalg.norm(np.concatenate((r1, r2)))`, follows both `u += r1` and `w += r2`. The mapping is original theta→theta, v→theta_tilde, z→theta_hat, u→u, w→u_tilde. Copies are made before a subsequent iteration can mutate arrays.

The quadratic loss calls original `ridge_prox`; Poisson calls original `poisson_prox`; ridge regularization calls original `ridge_regularizer_prox`. The source has no L1 proximal primitive. For the L1 case only, the explicitly allowed public-input callback `sign(nu)*max(abs(nu)-t*coefficient,0)` is supplied. This does not replace any original ADMM loop or consensus/dual update, but the L1 primitive itself is adapter-supplied and therefore is not evidence of a native Codex L1 implementation.

Dependencies: NumPy, SciPy, NetworkX. `bindings.json` identifies the original ADMM and original numeric helpers; the adapter-defined L1 callback is deliberately not claimed as a source binding.
