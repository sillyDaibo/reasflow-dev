# proxrr-reasflow independent adapter review

Decision: **approved within declared scope**. Approved for original ProxRR/FedRR driver and proximal updates with public objective/order inputs; original logistic gradients remain covered.

Approval means faithful execution/observation within the stated public-input scope, not agreement with the paper or correctness of the algorithm.

Reviewed the redacted public cases, adapter source, bindings and original CPU30 source only; no private contract, expected-value array, derivation script, prior adapter review or prior verdict was consulted.

Source and adapter hashes bind this static review. Execution success and numerical agreement require the separate runtime/provenance/comparison stage.

Synthetic problem callbacks cannot validate the displaced original objective/data/compression primitives. They must not be described as a full original end-to-end application reproduction.

Input mapping: x0, public regularizer coefficients, epoch/client orders and sample counts are supplied through original driver APIs. The RNG checks permutations against each actual source request.

For per-epoch gamma the adapter executes a one-epoch original ProxRR driver per public epoch, carrying only its returned x into the next API call. This is scoped to the source state consisting of x and the public schedule/orders, with decay/importance sampling disabled by defaults.

The public quadratic gradient is an input oracle. It preserves source-requested sample index, current point and requested normalization. The logistic case instantiates and calls the original logistic loss class, leaving its treatment of L2 observable.

prox_rr, original LogisticElasticNet.gradient_batch, original elastic_net_prox, fed_rr and _run are original. FedRR _partition and local loss construction supply public unequal client sizes; original rounding of local_n and server prox scale remain unchanged.

Observation timing uses the next line/return trace event after original x -= or z -= to copy true inner iterates; original proximal assignment is observed after execution; local endpoints and equal-weight aggregation are captured at their actual source statements.

This does not validate original quadratic/data factory behavior displaced by QuadraticInput. In ReasFlow the synthetic oracle does not inherit the original logistic extra-L2 gradient behavior; the distinct logistic public case retains coverage of that implementation.

FedRR core local update, aggregation and regularization are untouched. Original proximal n scaling and server scaling can therefore fail independently of adapter approval.

## Substitutions

- `QuadraticInput.gradient/gradient_batch/value` (problem_input): Public synthetic loss oracle and unobserved objective logging; original proximal map retained.
- `numpy.random.default_rng` (problem_input): Public epoch/client permutation input only, with exact consumption checks.
- `federated.LogisticElasticNet` (problem_input): Construct public quadratic local loss; no driver updates replaced.
- `sys.settrace` (observation): Observe actual completed gradient steps, aggregation and original proximal statements.
- `federated._partition` (problem_input): Supply the public unequal client partitions rather than a randomly repartitioned dataset.

No core algorithm replacement identified. Approval does not assert numerical match.

## Bound evidence

- public_digest: `40d00b6322666d157c66c99392f0cfd6b3f4648747ff77a719d7bff8d9597fb8`
- adapter_sha256: `64f2dafabd6eeb7aec1b9ff1f102501c323a629af6690b08d1dd00228ece2b72`
- workspace_digest: `f93e243d63415b3d1a74ce9cf365a33b3f242c17e5536084a742c41668a21777`
- bindings_digest: `f83335a8a3d0ff5897d5675a343f4f3886f29d6492cec2bc5998e8bedada0eca`
