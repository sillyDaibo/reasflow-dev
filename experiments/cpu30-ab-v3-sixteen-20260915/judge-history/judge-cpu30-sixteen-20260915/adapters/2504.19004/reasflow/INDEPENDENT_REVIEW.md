# Independent source/public adapter review

Reviewer: adapter16_c. Decision: approved (adaptation fidelity only).

The partial adapter is faithful: source has no usable fixed-eta interface, so it exposes only four actual first-event pre-update observations and explicitly blocks the rest.

problems.py:41-59 supports P=a/2,q=-a*c,r=a*c^2/2; native _precompute regenerates inverse Hessians and L from these public objective coefficients.

graphs.py:9-26 and 62-99 lexicographically order edges; adapter permutes public initial dual coordinates and observed edge indices consistently, with identical +first/-second orientation.

Blocked claim independently challenged: solvers.py:35 creates stepsizes but solve:95 ignores it and directly uses grad/L[e]. Constructor/solve have no eta argument. Replacing L would replace a core step mechanism. No such change is made.

Only trace lines 88/90 with t=0 emits actual initial cache, gradient, dual objective and selected edge. All post-update and later-event observations remain missing. Native solve still executes unchanged.

Approval covers adaptation fidelity and honest limited coverage; neither a full public experiment pass nor correctness of the unrequested coordinate-Lipschitz trajectory is asserted.

Original source was independently read. Public smoke executed with immutable source tree; no private comparison was run. Exact adapter, workspace, public JSON and bindings hashes are recorded in review.json and validated with validate_adapter_review.
