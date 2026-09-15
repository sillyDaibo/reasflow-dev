# beer-reasflow independent adapter review

Decision: **approved within declared scope**. Approved for genuine original BEER control flow, gradient locations, compression residuals and observed X/H/V/G state.

Approval means faithful execution/observation within the stated public-input scope, not agreement with the paper or correctness of the algorithm.

Reviewed the redacted public cases, adapter source, bindings and original CPU30 source only; no private contract, expected-value array, derivation script, prior adapter review or prior verdict was consulted.

Source and adapter hashes bind this static review. Execution success and numerical agreement require the separate runtime/provenance/comparison stage.

Synthetic problem callbacks cannot validate the displaced original objective/data/compression primitives. They must not be described as a full original end-to-end application reproduction.

Input mapping: client labels encode objective identity, public diagonal quadratics provide pointwise full deterministic gradients, initial_common_point and W enter the original driver, and eta/gamma/iterations map directly to original arguments.

The public compressor is implemented as an oracle because compression map is an explicit test input. It executes wherever the original driver calls compression; choice of residual/raw state and channel update is not rewritten.

Original run_decentralized executes unchanged with a model object. Initial x0 is copied once into the original float32 buffer before replication/gradients. Step 0 is captured before the original first x advance; step t is captured after v/gstate catch up and before the next x_new, giving the source staggered full-round cut.

State observations are copies only. Compression, tracking and descent state are never assigned by the adapter; public objective/compressor functions do not generate expected trajectories.

The model gradient retains float32 output and source float32 state behavior. The source executes a further x/h half-round after the final observed complete-round cut; this adapter reports only the declared complete-round state, not that later return state.

Original data preprocessing, logistic objective, stochastic sampling and compressor implementation are outside this scope. Only driver use of the prescribed compressor, including per-client call placement/residual arguments, is verified.

## Substitutions

- `SyntheticQuadratic model` (problem_input): Public deterministic objective and unobserved accuracy metadata.
- `core.compressor` (problem_input): Factory returns prescribed scale/top1 compressor.
- `run_decentralized x0 buffer` (problem_input): Public initial value injected once before replication, keeping original dtype.
- `sys.settrace` (observation): Copy original X/H/V/G at initialization and complete-round execution boundary.

No core algorithm replacement identified. Approval does not assert numerical match.

## Bound evidence

- public_digest: `57cfd36a2580d2cbb47f1506e7d817fe99073ee7cccad322b4317b866f289bb6`
- adapter_sha256: `87926725bc34e23ee02ace3c853235537f5cd94798f3fc12f123cd98799acd1e`
- workspace_digest: `313c9872057bbc4776df9bd9f648d20a411c39dd3d9421d6e485a083ebd9fd03`
- bindings_digest: `603d3a10b925fef3004fa81769adb256f16089745a323542314d4dea6dc2427b`
