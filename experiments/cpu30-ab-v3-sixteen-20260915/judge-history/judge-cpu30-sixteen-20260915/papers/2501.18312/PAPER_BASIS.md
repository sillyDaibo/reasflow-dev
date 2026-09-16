# Paper basis: 2501.18312

Only the supplied original PDF was used to construct the standard. No reproduction code, adapter, output, history, or other reports informed these values. contract.json records the source hash.

## Exact original-paper basis

- PDF pp.6-7, Section 2 and equation (1): separate positive and negative mass, independently sample each categorical distribution with replacement, and reconstruct with each sign's L1 mass divided by M. Page 7's explanation explicitly permits uniform `[0,1]` arguments transformed inside PPS. Equation (1) was visually verified.
- PDF p.8, Section 3 and equations (3),(5): the dual objective is `lambda^T b + f_star(-A^T lambda)` and primal recovery is `grad f_star(-A^T lambda)`. The deterministic dual oracle is `b-A*grad f_star(-A^T lambda)`. Signs were checked against the rendered page.
- PDF p.11, Algorithm 2, visually verified: `z_t` divides the accumulated alpha-weighted G by **beta_t**; `mu_{t+1}` mixes z with old lambda; the second point subtracts `alpha_{t+1}/beta_t * G_{t+1}`; lambda mixes that point with old lambda; primal output averages restored values at all mu points including initialization. The coefficient conditions immediately below the algorithm are respected.

The selected method is the generic affine-constrained Algorithm 2, which is fully specified in the paper. Algorithm 1's displayed pseudocode on p.9 omits a recurrence assigning its subsequent x values; it is not silently repaired or tested here. The decentralized Algorithm 3 and barycenter specialization are outside scope.

## Fixtures and genuine limitations

Two three-dimensional strongly convex quadratic primal objectives use positive-definite diagonal A and explicit right-hand sides. Their conjugates, dual gradients, and primal restoring functions are derived analytically. One fixture has two positive gradient coordinates, the other two negative ones, so the categorical quantization has a nontrivial effect in both sign channels across the cases. Both sign masses stay positive. Explicit decimal uniforms determine each categorical draw using an unambiguous strict-CDF convention; no random-number-library dependence is present.

The coefficients `alpha=[1,1,1.5,2]`, `beta=[4,5,6,7]`, `beta[-1]=4` obey the printed inequalities with L=1. Each fixture records initialization and three complete updates, including all dual stages, raw and quantized gradients, sampled indices, sign masses, restored primal values, weighted averages, residuals, and objective values. This tests the core algorithm rather than standalone quantization.

**Limited theorem scope:** the quadratic dual gradient is globally unbounded, although bounded on this finite visited set. Thus the fixtures do not instantiate Section 2's uniform bound `||g(x,xi)||_1 <= B` over all points. They validate the displayed finite algebraic recurrence only and must not be described as verifying the large-deviation convergence theorems. This limitation is also present in the public contract, not hidden from the adapter. No artificial clipping or substituted optimizer has been added to force that hypothesis.

All expectations and categorical comparisons are derived using exact Fraction arithmetic, with one final conversion to JSON numbers. The rational trace is private. `atol=rtol=1e-10` accommodates ordinary double precision evaluation without masking changes in the coefficient denominators, signed scaling, or recovery weights. This authoring note is not an independent paper review.
