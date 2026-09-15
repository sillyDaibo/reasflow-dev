# Independent public/source-only adapter review

Original ProxSkip solver and matching affine finite-sum operator execute unchanged; trace captures actual operator, proposal, worker, control and communication-count states after each requested local update.

- Inspected vip_repro.algorithms.proxskip and AffineVIP.client directly; public operators are passed as one exact component and retain source float dtype and full local operator normalization.
- Both cases have equal initial worker states, so the original shared-x0 argument is sufficient. Nonzero h0 is injected only once before the first while iteration.
- The supplied Bernoulli outcomes are consumed in source order; deterministic full operators require no other RNG draws. Source branches and update order remain unchanged.
- Source terminates on communication count, while the public budget is four local updates. The adapter sets a nonbinding communication cap and stops through a sentinel only at the next while condition after the fourth completed update, before another update or draw. This is a finite execution window, not a rewritten step.
- mean_x is the explicitly requested diagnostic mean of real worker states; it does not feed the algorithm. Public-only readonly smoke produced 24 required observations per case.

Substitution audit:
- LinearFiniteSumVIP/AffineVIP constructor (problem_input): Public matrices and offsets use the original matching affine problem class with one component.
- trace initial h and RNG (problem_input): Initial control state and declared Bernoulli realization only.
- trace observation/window (observation): Reads actual original locals after completed steps and ends at the public finite budget; creates no state updates.

Reviewed bytes: 827c0f59af2351f24f76e3cafed172d4004f89bf4ec3b34ffecd5d9d9f635b8c
Workspace digest: fec4282d740118d3af73d08ef4ef5cf5387088e4c216afdfecefc682a1a1b222
No papers, private answers, derivations, historical reviews, or numerical Judge results were read. Approval concerns adaptation fidelity, not algorithm correctness.
