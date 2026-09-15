# rsa-reasflow independent adapter review

Decision: **approved within declared scope**. Approved for genuine original RSA updates on supplied quadratic objectives and prescribed Byzantine messages; source normalization and update ordering remain observable.

Approval means faithful execution/observation within the stated public-input scope, not agreement with the paper or correctness of the algorithm.

Reviewed the redacted public cases, adapter source, bindings and original CPU30 source only; no private contract, expected-value array, derivation script, prior adapter review or prior verdict was consulted.

Source and adapter hashes bind this static review. Execution success and numerical agreement require the separate runtime/provenance/comparison stage.

Synthetic problem callbacks cannot validate the displaced original objective/data/compression primitives. They must not be described as a full original end-to-end application reproduction.

Input mapping: public initial master/regular-worker vectors, penalty norm, lambda and Byzantine message arrays map to original state/arguments; master center must be zero and weight_decay/l2 is 1.

Original norm_subgradient and run_training execute unchanged. The source divides local objective gradients by total worker count and forms master penalties using transmitted post-worker-update models; the adapter leaves both choices intact.

Observation timing: objective-gradient and norm-return copies are taken during the real step; penalty is read from its original local; completed master/workers are copied after updates. Master regularizer gradient is derived solely from the original pre-update operand and coefficient, never fed back.

The original float32 10-class allocation is retained and vectors occupy row zero. Initialization injection happens once before the loop; the fixed alpha0/sqrt(step+1) schedule is not overridden. Only the matching prefix executes, and subsequent requested observations are explicitly blocked.

No claim is made about original softmax objective or attack-generator correctness; prescribed attacks and quadratic gradient replace these problem boundaries.

## Substitutions

- `softmax_gradient` (problem_input): Return supplied quadratic objective gradients at the exact source-requested point; original driver normalization remains.
- `_attack_message` (problem_input): Supply the external Byzantine sender vectors; ReasFlow honest-sender helper remains original.
- `sys.settrace` (observation): Copy original norm return values and update frame locals; no iterative state overwrite.
- `run_training initial theta/local buffers` (problem_input): One-time insertion of supplied initial values, preserving float32 allocation and zero unused coordinates.

No core algorithm replacement identified. Approval does not assert numerical match.

## Bound evidence

- public_digest: `716796aee029b4dbbcc71ab959f2bc1d3a925c1a99e7cb5c7144308fb706a620`
- adapter_sha256: `3084c89c5eddedacba1d0229dc3496d99ba332709c6fd994e16f5159d1fa23e0`
- workspace_digest: `2db70b936737c54b45670419752616ceea83bae233e4f928be62bb0e0173de78`
- bindings_digest: `008aae55885bc3e8430d03257bc552d61c2052a30e95f657d3e94a45719b3496`
