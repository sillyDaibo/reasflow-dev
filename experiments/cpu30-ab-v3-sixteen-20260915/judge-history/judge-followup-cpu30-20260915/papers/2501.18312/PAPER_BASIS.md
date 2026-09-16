# Paper-only basis: 2501.18312 Algorithm 3

Source: `datasets/benchmarks/cpu30_v1/input/2501.18312/paper.pdf`, “Decentralised convex optimisation with probability-proportional-to-size quantization”. The PDF SHA-256 is bound in `contract.json`. Relevant complete PDF pages 17–20 were rendered and inspected; pp. 6–7, 8–9 and 11 provide the oracle and coefficient definitions. No implementation, adapter, run, historical comparison, or other person's interpretation was consulted to derive these cases.

## Scope and definition limits

The mandatory target is the literal **p. 17 Algorithm 3 dual recurrence**, supplied with the p. 20 Lemma 3 local barycenter oracle. It is not a generic Algorithm 2 experiment: local probability oracles, their finite-sample quantization, graph coupling, unequal node degrees, and synchronous updates are exercised directly. It does not assert a converged barycenter after two iterations.

Three paper ambiguities are material:

1. Algorithm 3 does not initialize the primal `x_0`, and the restoring call `x^i(mu_i,xi_i)` omits time subscripts. Neither an invented initialization nor an inferred time index is made a mandatory expected value. No primal recovery, `x_T`, objective, or optimum assertion occurs in the public observation schema.
2. The pseudocode writes a sum over neighbors even though an ordinary Laplacian has a nonzero diagonal. Section 5, p. 18, explicitly derives the distributed update using `W x`. Thus the contract uses the supplied full matrix `W`, including each local diagonal term. This convention is public and does not replace W by adjacency or a normalized Laplacian.
3. Section 5, p. 18, denotes plain lambda as `sqrt(W) bold_lambda`, while the WB specialization on p. 19 uses `m sqrt(W) bold_lambda`. The latter transformation can introduce an `m W` update when derived from the global dual. The contract therefore explicitly tests p. 17 itself with its supplied local oracle and its printed `W`, with the local argument passed directly to the Lemma 3 formula. It does **not** claim to resolve the inconsistent global-dual coordinate notation or to verify Eq. (8) under every scaling convention. No extra factor `m` is silently inserted or tested.

The number of samples `r` and PPS draws `M` is constant within each case, avoiding the pseudocode's call-time indexing ambiguity for these schedules. Section 4.3's optimized noise schedules concern complexity guarantees; the finite Algorithm 3 inputs permit the explicit admissible schedules used here.

## Paper formulas used

Lemma 3, p. 20, gives the conjugate-gradient sample at local argument `v`, source point `xi`, support points `y_h`, and positive gamma:

`p_h(v,xi) = exp((v_h - (y_h-xi)^2)/gamma) / sum_l exp((v_l - (y_l-xi)^2)/gamma)`.

Squared distance is a selected continuous nonnegative cost allowed by Section 6.1, not a claim that the paper requires this sole cost. Section 2, pp. 6–7, averages the `r` sample gradients **before** quantization. The resulting vector has nonnegative entries and unit l1 mass. Eq. (1) consequently reduces to an empirical frequency vector `G_h = count(k=h)/M`; the negative part has zero mass. The p. 7 paragraph explicitly permits fixed uniform numbers as the random arguments. The public contract uses inverse CDF with one-based indices and strict `u < cdf` boundaries.

Define `H_s = W G_s`, `S_s = sum_(k=0)^s alpha_k H_k`. Algorithm 3 gives:

- `A_0 = alpha_0`, `mu_0 = 0`, `lambda_0 = -alpha_0 H_0/beta_0`.
- For `s=1,2`: `A_s=A_(s-1)+alpha_s`, `tau=alpha_s/A_s`, `z_(s-1)=-S_(s-1)/beta_(s-1)`.
- `mu_s=tau z_(s-1)+(1-tau) lambda_(s-1)`; evaluate all node oracles and quantize, then compute `H_s`.
- `hat_mu_s=z_(s-1)-alpha_s H_s/beta_(s-1)` and `lambda_s=tau hat_mu_s+(1-tau) lambda_(s-1)`.

Public observation names and step conventions are fully defined in `parameters`. Every required quantity at calls 0, 1 and 2 is numerically listed in `contract.json`; `derive_contract.py` reproduces all of them using 60-digit Decimal arithmetic.

## Case 1: two nodes and two support points

The source laws are Uniform[0,1/2] and Uniform[1/2,1], both continuous probabilities on bounded X=[0,1]. All fixed source samples lie strictly in the corresponding supports. Target support is [0,1], gamma=1/2, r=2, M=4. Therefore costs are at most 1, probabilities are legal and B=1. At initialization, the first component of node 1's minibatch is `(sigmoid(1.6)+sigmoid(0.4))/2`; node 2's is its complement. This checks the cost sign, gamma, normalization and averaging order.

W=[[1,-1],[-1,1]] has spectral norm 2. The p. 18 conservative `L=m||W||/gamma` is 8, below every beta=[16,20,24]. alpha=[1/2,3/4,1] has alpha_0 in (0,1]. For t=1, `alpha_t² beta_t=11.25 <= beta_(t-1) A_t=20`; for t=2, `24 <=45`. Beta is increasing.

The complete rational graph and final-dual trace is:

| call s | G rows | H=WG rows | A | lambda rows |
|---|---|---|---|---|
| 0 | (3/4,1/4); (1/4,3/4) | (1/2,-1/2); (-1/2,1/2) | 1/2 | (-1/64,1/64); (1/64,-1/64) |
| 1 | (1/2,1/2); (3/4,1/4) | (-1/4,1/4); (1/4,-1/4) | 5/4 | (-11/1280,11/1280); (11/1280,-11/1280) |
| 2 | (3/4,1/4); (1/4,3/4) | (1/2,-1/2); (-1/2,1/2) | 9/4 | (-199/11520,199/11520); (199/11520,-199/11520) |

In particular, both loop iterations change the dual state, and the first iteration reverses the graph-gradient sign. At s=1, tau=3/5 and z_0=lambda_0. At s=2, tau=4/9, `S_1` row 1=(1/16,-1/16), so `z_1` row 1=(-1/320,1/320). These are nontrivial weighted-history observations.

## Case 2: three-node path and three support points

The graph is the unweighted path 1–2–3, W=[[1,-1,0],[-1,2,-1],[0,-1,1]]. Its eigenvalues are 0,1,3, hence L=9 for m=3 and gamma=1. The three continuous uniform source laws and all source samples are explicitly given in the public input on X=[-1,1]. Target support is [-1,0,1]; costs are bounded by 4 and B=1. r=2, M=5.

alpha=[1,1/2,5/4], beta=[24,30,36]. Beta exceeds L and increases. At t=1 the coefficient condition is `7.5 <=36`; at t=2 it is `56.25 <=82.5`. A=(1,3/2,11/4), and the two mixing weights are 1/3 and 5/11.

| call s | G rows | H=WG rows |
|---|---|---|
| 0 | (3,1,1)/5; (1,2,2)/5; (1,1,3)/5 | (2,-1,-1)/5; (-2,2,0)/5; (0,-1,1)/5 |
| 1 | (3,1,1)/5; (1,2,2)/5; (1,2,2)/5 | (2,-1,-1)/5; (-2,1,1)/5; (0,0,0) |
| 2 | (3,1,1)/5; (1,3,1)/5; (1,1,3)/5 | (2,-2,0)/5; (-2,4,-2)/5; (0,-2,2)/5 |

The final lambda rows are `(-3/110,23/1320,13/1320)`, `(3/110,-43/1320,7/1320)`, and `(0,1/66,-1/66)`. The middle node's degree-two diagonal and both neighbor messages affect the result. A non-neighbor has weight zero. One node has zero graph gradient at one call, while the global graph gradient and both overall iterations remain nontrivial.

## Numerical checks, tolerance and publication boundary

The derivation was cross-checked by recomputing every softmax with ordinary `math.exp`, categorical selections independently, and all graph and acceleration arithmetic with exact `fractions.Fraction`. Every required observation agreed to below 1e-14. Exact lambda row sums and column sums are zero, as required by these probability gradients and the Laplacian.

The minimum distance of any fixed uniform to an internal CDF boundary is approximately 0.0457745 for case 1 and 0.00593883 for case 2. Thus tolerance does not conceal borderline categorical decisions. Absolute tolerance 1e-10 and relative tolerance 1e-9 allow routine double-precision exponential and summation differences; they are orders of magnitude below the deliberately activated graph/quantization changes. Discrete indices are separated by integers, so this tolerance still effectively requires exact indices.

`validate_contract` passed for 2 cases and 365 numeric leaves. The public file was produced using the schema's `public_contract` and contains inputs, parameters and observation coordinates only. Expected values and derivations remain private. The public input was frozen before any original-code interface work; no implementation result informed its selection. This file records derivation and limitations, **not independent reviewer approval**.
