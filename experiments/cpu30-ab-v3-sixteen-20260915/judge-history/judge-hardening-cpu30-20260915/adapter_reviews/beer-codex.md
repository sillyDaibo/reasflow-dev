# beer-codex independent adapter review

Decision: **approved within declared scope**. Approved for genuine original BEER control flow, gradient locations, compression residuals and observed X/H/V/G state.

Approval means faithful execution/observation within the stated public-input scope, not agreement with the paper or correctness of the algorithm.

Reviewed the redacted public cases, adapter source, bindings and original CPU30 source only; no private contract, expected-value array, derivation script, prior adapter review or prior verdict was consulted.

Source and adapter hashes bind this static review. Execution success and numerical agreement require the separate runtime/provenance/comparison stage.

Synthetic problem callbacks cannot validate the displaced original objective/data/compression primitives. They must not be described as a full original end-to-end application reproduction.

Input mapping: client labels encode objective identity, public diagonal quadratics provide pointwise full deterministic gradients, initial_common_point and W enter the original driver, and eta/gamma/iterations map directly to original arguments.

The public compressor is implemented as an oracle because compression map is an explicit test input. It executes wherever the original driver calls compression; choice of residual/raw state and channel update is not rewritten.

Original runner.run_experiment, BEER.initialize and BEER.step execute. The runner computes the next-point gradient location and supplies it to the original step; the adapter never predicts that location. Initialization/method-return events copy row-major internal arrays transposed to public [dimension][client].

State observations are copies only. Compression, tracking and descent state are never assigned by the adapter; public objective/compressor functions do not generate expected trajectories.

Original dataset loader, initial-point generator, topology constructor, logistic loss and accuracy are replaced at input/logging boundaries; run_experiment output goes into a temporary directory.

Original data preprocessing, logistic objective, stochastic sampling and compressor implementation are outside this scope. Only driver use of the prescribed compressor, including per-client call placement/residual arguments, is verified.

## Substitutions

- `runner.load_a9a` (problem_input): Construct synthetic clients with public objective identities.
- `runner._initial_params` (problem_input): Public common initial point.
- `runner.mixing_matrix` (problem_input): Public W.
- `runner.logistic_loss_gradient` (problem_input): Public deterministic quadratic objective at the original runner-selected point.
- `runner.logistic_accuracy` (problem_input): Unobserved logging constant.
- `algorithms.compress` (problem_input): Public specified scale/top1 compressor.
- `sys.settrace` (observation): Copy original X/H/V/G at initialization and complete-round execution boundary.

No core algorithm replacement identified. Approval does not assert numerical match.

## Bound evidence

- public_digest: `57cfd36a2580d2cbb47f1506e7d817fe99073ee7cccad322b4317b866f289bb6`
- adapter_sha256: `7b2935aeae1cc55d60b78ff9bcad8e1b9ec6f26cca15748deeb58e7d402fa5d3`
- workspace_digest: `95e9c5e61f2cb08899d56de18c5b6ee73e7c7de5c5ecbe7b7097e57759afce11`
- bindings_digest: `8b7af0f521ed803b72826aadc3248feda907ebde4dfe92cfaf0b7b33a48388bf`
