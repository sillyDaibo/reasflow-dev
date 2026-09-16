# Independent public/source-only adapter review

Faithful execution of the original DASHA-PAGE update, Rand-1 compressor and bucketed coordinate median with necessary public finite-sum objective callbacks and declared adversarial/random inputs.

- Directly inspected the original DASHA-PAGE loop, original RandK, bucketed coordinate median, sampler entry points, initialization and objective implementation. Public readonly smoke completed both cases with 24 required actual observations.
- Public quadratic component mean uses exactly two components per honest worker and all ten components for the global objective; malicious worker is excluded from the objective but included in the original six-worker aggregation.
- RNG supplies PAGE coins, same component index for both points in a difference, Rand-1 coordinates, and four bucket permutations including initialization. Refresh steps consume no component draws. Original RandK scales by d/k and original aggregation returns feed the real algorithm.
- Arbitrary public Byzantine states replace only attacker generation. Initial malicious state is supplied before initial aggregation. Compressor wrapper calls original and returns its value unchanged; true bucket arrays are traced at the original aggregation return.
- Full gradients generate the declared initial honest h and g at supplied x0, rather than overwriting their updates. Native float dtype, correction arithmetic, branch order and finite loop are unchanged.
- Codex TwoGroupQuadraticObjective has fixed identity Hessian (grad=x+offset), and LogisticObjective cannot represent these heterogeneous component diagonal Hessians; custom objective is necessary. _run_dasha chooses a component before calling _gradient with batch_size equal selected-row count, so callback batch_gradient does not bypass any further random selection. Original correction expression at algorithms.py:182-184 is preserved.

Substitution audit:
- public quadratic gradient/loss callbacks (problem_input): Replace only problem-specific logistic/fixed-identity objective evaluations that cannot express the supplied heterogeneous finite sum; selected-row means retained.
- initial x / arbitrary Byzantine state input (problem_input): Supplies public starting point and adversary messages; honest updates and aggregation untouched.
- deterministic RNG (problem_input): Supplies declared supported PAGE, sample, compressor and permutation outcomes in actual source consumption order.
- randk wrapper and bucket/state trace (observation): Observes original compressor argument/output and true updated local/server states; no independent update is computed.

Reviewed bytes: 9e3186590085d8fe7b66f6f5fdd7838077fe7a727c0c864ec1738af5a1963493
Workspace digest: dd0c1dd40e83d52a9410b5e55f2d9e1b0e907f9f97e2841d10c5f41b6ce1a076
No papers, private answers, derivations, historical reviews, or numerical Judge results were read. Approval concerns adaptation fidelity, not algorithm correctness.
