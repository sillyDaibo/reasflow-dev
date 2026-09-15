# BEER Codex public-only adapter review

Only the supplied BEER public_cases.json and the designated Codex workspace Python source were consulted. No BEER paper, private contract, expected values, derivation, prior output or repository test was read. The adapter is a self-contained single file and reads OPTIREPRO_CASES and OPTIREPRO_WORKSPACE at runtime.

## Original execution and bindings

The adapter calls the unmodified beer_repro.runner.run_experiment, which creates and initializes the unmodified beer_repro.algorithms.BEER and calls its original step. Crucially, the original runner itself computes the next point supplied to the gradient oracle; the adapter contains no model update or predicted-next-point formula. The original class keeps client-by-dimension arrays, so copying and transposing these arrays provides the public dimension-by-client observation layout.

Input-boundary substitutions are synthetic client data through load_a9a, the common point through _initial_params, the public W through mixing_matrix, the synthetic quadratic objective and exact gradient through logistic_loss_gradient, and the deterministic public compressor through algorithms.compress. The original ClientData.batch still executes. The injected compressor supports the specified Top1 tie rule and scale map and is called by the original per-client residual loops. No original optimizer state update is replaced. The driver selects its existing identity compression label solely for peripheral communication-bit bookkeeping; numerical compression is the explicitly supplied callback. Accuracy is an unused constant fixture metric. Original driver artifact writes run inside a temporary directory that is removed, and no generated experiment artifacts are read.

## Observation timing and precision

A sys.settrace observer copies states after BEER.initialize returns (step 0) and after BEER.step returns (step equal to original self.round). It never writes optimizer arrays. The original driver and state machine retain their NumPy float64 arithmetic, update ordering, allocation, and initial h/g/gradient state. sys.setprofile is not changed, allowing an external original-function provenance profiler to operate alongside the observer. The prior trace is restored on exit.

## Public smoke result and limits

Both supplied public cases executed successfully in /tmp/optirepro-paper-judge-20260915/bin/python with PYTHONDONTWRITEBYTECODE=1. Each emitted all 16 requested observations, and the process emitted exactly one OPTIREPRO_OBSERVATIONS line. No numeric comparison to private expected values was performed and no numeric pass is claimed. Public smoke used preinstalled NumPy 2.0.2. environment_actions.json requests NumPy installation for each fresh replay virtual environment. Original import-time dependencies besides NumPy are standard-library modules; optional plotting is handled by the original driver when unavailable. Original workspaces and judge pipeline were not modified.
