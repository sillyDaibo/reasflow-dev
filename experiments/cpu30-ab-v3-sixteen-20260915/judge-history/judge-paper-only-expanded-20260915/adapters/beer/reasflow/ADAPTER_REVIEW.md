# BEER ReasFlow public-only adapter review

Only the supplied BEER public_cases.json and the designated ReasFlow workspace Python source were consulted. No BEER paper, private contract, expected values, derivation, prior output or repository test was read. The adapter is a self-contained single file and reads OPTIREPRO_CASES and OPTIREPRO_WORKSPACE at runtime.

## Original execution and inputs

The adapter invokes the unmodified beer_repro.core.run_decentralized once per public case, with its algorithm='beer'. Inputs are synthetic client datasets, a SyntheticQuadratic model implementing the public objective and gradient, the public mixing matrix, step sizes and iteration count. The model preserves the source model gradient float32 output convention. The source compressor factory is supplied with the deterministic public Top1 or scale callback; the original client residual compression loops execute. Its identity label only selects peripheral communication-bit bookkeeping, not numerical compression. Accuracy is an unused constant fixture metric.

The function normally allocates x0 from an RNG and converts it to float32. A trace hook copies the specified public initial point into that existing x0 allocation immediately before the original np.repeat creates client states and before any gradient call. This is solely an initial-input substitution: dtype remains float32 and every subsequent optimizer state is changed only by original source statements. In particular the adapter does not recompute updates, fix precision, remove casts, or predict gradient-request locations.

## Staggered observation timing

The original driver first initializes v/h/gstate, then performs one x descent and h compression before the loop. Each loop updates v/gstate at the current x and only then advances x/h again. Observations therefore use source phases rather than the driver's returned history index:

- Step 0 is copied just before the initial x descent, with original x, v, h and gstate present.
- Step t=1,2,3 is copied immediately before the original x_new assignment in loop iteration t. At this point x/h already represent that model round, and v/gstate have just completed the matching tracking phase.

This phase alignment reads actual original arrays and involves no reconstructed values. After the last requested snapshot the original function continues through its ordinary next x/h advance and return; that extra model phase is not a requested observation. The source's initial float32 arrays, model float32 gradients, float64 mixing intermediates, and explicit x_new.astype(float32) remain unchanged. Consequently numerical differences due to source precision remain visible. Arrays are copied and transposed to the public dimension-by-client layout. Source line boundaries are resolved from exact statements and must be unique; unsupported source changes are reported as blocked rather than guessed. The trace never replaces an update and does not change sys.setprofile; the previous trace and compressor factory are restored on exit.

## Public smoke result and limits

Both supplied public cases executed successfully in /tmp/optirepro-paper-judge-20260915/bin/python with PYTHONDONTWRITEBYTECODE=1. Each emitted all 16 requested observations and the process emitted exactly one OPTIREPRO_OBSERVATIONS line. No numeric comparison to private expected values was performed and no numeric pass is claimed. Public smoke used preinstalled NumPy 2.0.2; environment_actions.json requests NumPy installation for each fresh replay virtual environment. Other import-time dependencies are standard-library modules. Original workspaces and judge pipeline were not modified.
