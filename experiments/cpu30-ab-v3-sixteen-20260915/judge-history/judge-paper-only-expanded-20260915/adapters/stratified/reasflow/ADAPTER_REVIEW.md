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

## ReasFlow original bindings and trace timing

`strat_models/fit.py::fit_stratified_model` is the unmodified complete original iteration. It retains the original Jacobi preconditioner and sparse SciPy CG with rtol=1e-7, atol=0 and default max_cg_iterations=10. These are not tightened or replaced. Existing tau_incr=tau_decr=1 and min_rho=max_rho=the requested rho disable the optional rho adaptation without changing source code or rescaling state afterward.

Source line 110, immediately before `primal_norm = float(np.linalg.norm(primal))`, follows both `u += theta-theta_hat` and `u_tilde += theta_tilde-theta_hat`. Original local variable names already match the five public names. Copies are taken only after both duals update.

The original `sum_squares_loss.prox` receives the public quadratic sufficient statistics. Original `poisson_loss.prox`, `sum_squares_reg.prox`, and `L1_reg.prox` are called for their respective cases; no proximal implementation is replaced. The `_call_prox` helper is also original. The parameter shape `(n,)` uses the original vector-compatible proximal implementation and produces the requested K by n observations.

Dependencies: NumPy, SciPy, scikit-learn. The latter is required by the original loss module's top-level LabelEncoder import even though the quadratic/Poisson probes do not use label encoding.
