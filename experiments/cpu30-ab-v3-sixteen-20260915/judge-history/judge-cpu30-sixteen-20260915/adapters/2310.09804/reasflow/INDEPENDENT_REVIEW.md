# Independent public/source-only adapter review

Faithful execution of the original DASHA-PAGE update, Rand-1 compressor and bucketed coordinate median with necessary public finite-sum objective callbacks and declared adversarial/random inputs.

- Directly inspected the original DASHA-PAGE loop, original RandK, bucketed coordinate median, sampler entry points, initialization and objective implementation. Public readonly smoke completed both cases with 24 required actual observations.
- Public quadratic component mean uses exactly two components per honest worker and all ten components for the global objective; malicious worker is excluded from the objective but included in the original six-worker aggregation.
- RNG supplies PAGE coins, same component index for both points in a difference, Rand-1 coordinates, and four bucket permutations including initialization. Refresh steps consume no component draws. Original RandK scales by d/k and original aggregation returns feed the real algorithm.
- Arbitrary public Byzantine states replace only attacker generation. Initial malicious state is supplied before initial aggregation. Compressor wrapper calls original and returns its value unchanged; true bucket arrays are traced at the original aggregation return.
- Full gradients generate the declared initial honest h and g at supplied x0, rather than overwriting their updates. Native float dtype, correction arithmetic, branch order and finite loop are unchanged.
- ReasFlow quadratic.run_quadratic enforces 20 honest workers, fixed identity Hessian, no PAGE Bernoulli sampling, and fixed group inputs; it cannot replace the general PAGE path for these public cases. core.run retains split_clients and _batch_gradient; row IDs carried as labels make the public callback respect original selected rows. Source-derived p=.5 and momentum=1/3 match the public inputs without any tuning override. Original correction at core.py:411-413 is preserved.

Substitution audit:
- public quadratic gradient/loss callbacks (problem_input): Replace only problem-specific logistic/fixed-identity objective evaluations that cannot express the supplied heterogeneous finite sum; selected-row means retained.
- initial x / arbitrary Byzantine state input (problem_input): Supplies public starting point and adversary messages; honest updates and aggregation untouched.
- deterministic RNG (problem_input): Supplies declared supported PAGE, sample, compressor and permutation outcomes in actual source consumption order.
- randk wrapper and bucket/state trace (observation): Observes original compressor argument/output and true updated local/server states; no independent update is computed.

Reviewed bytes: bbe3fb709de9b6b28a5328ca36ed781c8f503f18e18d33155a31eb9dddd76580
Workspace digest: c397b95a7ab8d180543645de3530833b74e0ed92b7002c8519731e3ca463c5ed
No papers, private answers, derivations, historical reviews, or numerical Judge results were read. Approval concerns adaptation fidelity, not algorithm correctness.
