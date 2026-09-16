# rsa-codex independent adapter review

Decision: **approved within declared scope**. Approved for genuine original RSA updates on supplied quadratic objectives and prescribed Byzantine messages; source normalization and update ordering remain observable.

Approval means faithful execution/observation within the stated public-input scope, not agreement with the paper or correctness of the algorithm.

Reviewed the redacted public cases, adapter source, bindings and original CPU30 source only; no private contract, expected-value array, derivation script, prior adapter review or prior verdict was consulted.

Source and adapter hashes bind this static review. Execution success and numerical agreement require the separate runtime/provenance/comparison stage.

Synthetic problem callbacks cannot validate the displaced original objective/data/compression primitives. They must not be described as a full original end-to-end application reproduction.

Input mapping: public initial master/regular-worker vectors, penalty norm, lambda and Byzantine message arrays map to original state/arguments; master center must be zero and weight_decay/l2 is 1.

Original norm_subgradient and rsa_step execute unchanged. The source divides local objective gradients by total worker count and forms master penalties using transmitted post-worker-update models; the adapter leaves both choices intact.

Observation timing: objective-gradient and norm-return copies are taken during the real step; penalty is read from its original local; completed master/workers are copied after updates. Master regularizer gradient is derived solely from the original pre-update operand and coefficient, never fed back.

Every requested alpha is supplied through rsa_step API, retaining original float64 state arrays.

No claim is made about original softmax objective or attack-generator correctness; prescribed attacks and quadratic gradient replace these problem boundaries.

## Substitutions

- `softmax_gradient` (problem_input): Return supplied quadratic objective gradients at the exact source-requested point; original driver normalization remains.
- `attack_message` (problem_input): Supply the external Byzantine sender vectors; ReasFlow honest-sender helper remains original.
- `sys.settrace` (observation): Copy original norm return values and update frame locals; no iterative state overwrite.

No core algorithm replacement identified. Approval does not assert numerical match.

## Bound evidence

- public_digest: `716796aee029b4dbbcc71ab959f2bc1d3a925c1a99e7cb5c7144308fb706a620`
- adapter_sha256: `9fa52dfc45b622bdf9e938ca12c71d6f216c9120614357a6fa5e730ae347fa6f`
- workspace_digest: `14c406f945d47687338675f6beec35c133ab7523bd01ac60ce620c9b4bcd186b`
- bindings_digest: `a7ec21328f9954eb3937eeb3a18add31ab4a34945fcc4eed85cb6dac9dde4f97`
