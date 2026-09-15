# Independent public/source-only adapter review

Approved faithful partial signed-PPS component execution with explicit missing full-algorithm states; source inspection supports the generic affine Algorithm 2 interface block.

- Challenged the partial/block claim by inspecting every algorithm/PPS entry point in the original workspace. The only full solver is a graph barycenter specialization with simplex-valued objective oracle and hardcoded acceleration schedule; there is no generic affine Algorithm 2 API with public alpha/beta arrays.
- The public experiment explicitly excludes Algorithm 3 and uses signed affine quadratic conjugate gradients. Routing it through the barycenter solver would require replacing simplex compression, graph mixing and coefficient mechanisms, rather than merely supplying an objective input.
- The original signed pps_quantize helper is genuinely callable and is used once on the public initial conjugate-oracle input. Its original positive/negative splitting, sign masses, count scaling and returned vector remain intact. The original full solver never calls this signed helper.
- Only five initial component observations are reported: actual PPS input and return, original traced sign masses, and actual injected categorical indices. mu/lambda, accumulated dual state and primal restoration are not synthesized; all 41 remaining schema entries are missing/blocked.
- The public initial oracle expression is an allowed problem input at mu0, not a reconstructed algorithm update. Inverse CDF uses the public uniforms and original probability values for each sign with replacement. Original dtype preserved.
- Public-only readonly smoke completed both cases with 5 actual observations and 41 missing entries each. Approval certifies truthful limited adaptation, not full Algorithm 2 coverage.
- Codex run_decentralized uses simplex_pps (rejects negative and non-unit mass), laplacian multiplication and fixed alpha=(t+2)/(2sqrt(2)); pps_quantize is separate in pps_quantization.py.

Substitution audit:
- initial public conjugate oracle (problem_input): Computes the declared deterministic oracle only at mu0 as input to original signed PPS; no recurrence or lambda is manufactured.
- RNG.multinomial/choice (problem_input): Supplies public categorical uniforms through inverse CDF; original probability normalization and PPS mass/count arithmetic are retained.
- pps_quantize input/return/local trace (observation): Reports true component input, original return and sign masses; sampled indices are the actual supplied draws.

Reviewed bytes: 5a8daf8c7efc1b84617a101ef3feeebe839db63538c925fd34f899873dc15b6f
Workspace digest: efa1eca0bf5ea5a88625843c5bd05c7d580601a67685501c3d7675dd17602622
No papers, private answers, derivations, historical reviews, or numerical Judge results were read. Approval concerns adaptation fidelity, not algorithm correctness.
