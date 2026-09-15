# Paper-only review: 2102.06704

Source boundary: only the specified original paper PDF, the contract schema, global AGENTS.md and the PDF skill were read. No implementation, run directory, benchmark metadata, card, existing expected values, repository documentation or external source was consulted. The synthetic inputs were chosen before any implementation inspection. The standard must remain frozen when an implementation is later evaluated.

## Paper interpretation and visual checks

The PDF is “Proximal and Federated Random Reshuffling,” arXiv:2102.06704v1 (12 February 2021), 21 pages. Physical PDF pages 1, 2, 3, 7, 8 and 21 were rendered with PyMuPDF at 1.4x and inspected using view_image. On page 3, Algorithm 1 lines 4–7 initialize the epoch, evaluate n sequential sample gradients, and apply exactly one prox with coefficient gamma_t*n. Page 7 Algorithm 3 lines 4–9 resets local models to the global state, executes each complete local data pass, averages devices with 1/M, and uses coefficient gamma*N/M on R. Thus unequal local sample counts must not silently become sample-weighted server averaging. Page 21 supplies the exact elastic-net proximal formula. Page 8 Eq.(14) specifies the logistic loss with labels in {0,1}.

## Three frozen experiments

1. **proxrr_quadratic_three_epochs**: 3 two-dimensional diagonal quadratic components, different centers/curvatures, three supplied permutations and stepsizes 1/8, 1/16, 1/8. Nonzero elastic-net regularization acts only at each epoch end. All 9 inner vectors and 3 outer iterates are required.
2. **proxrr_logistic_elastic_net_three_epochs**: the paper's logistic loss with 3 samples in 2 dimensions, three supplied permutations and decreasing supplied epoch stepsizes. lambda1=0.3 and lambda2=0.4 produce a nonzero first coordinate and a thresholded zero second coordinate after every epoch. All 9 inner vectors and 3 outer iterates are required. This exercises the nonlinear loss and a proximal branch absent from the first experiment.
3. **fedrr_unequal_clients_three_rounds**: 2 heterogeneous clients with 2 and 3 quadratic samples, three rounds and changing per-client permutations. gamma=1/8 gives alpha=5/16, threshold=1/32 and denominator=37/32. Each round records the first local update, local endpoints, the unregularized equal-weight average, and the new global model. Local vectors diverge, server regularization is nonzero, and device-weighted and sample-weighted averages differ in every round.

The public inputs specify objectives, gradient normalization, regularizers, all coefficients, explicit sample order, state naming and step indexing. Observations are algorithm states only; optimizer counters, proxy flags, convergence quantities and diagnostic packaging are not required. Tolerances (atol=1e-10, rtol=1e-9) accommodate ordinary binary64 arithmetic without accepting mechanism-scale deviations.

## Independent arithmetic verification

The quadratic and federated oracles use exact Fraction arithmetic. Each local sequence is independently checked against affine-map composition. Every rational proximal update satisfies coordinatewise KKT conditions; federated outputs also satisfy product-space consensus optimality. Logistic expected values use 80-digit Decimal exponentials and are independently checked against a separately evaluated binary64 recurrence at every inner and outer step (difference < 2e-15). The derivation text in contract.json contains the complete exact-fraction or high-precision trajectory. The schema validator is imported directly from the sole allowed schema file and validates the complete contract and the actual PDF hash.

## Scope and caveats

These tests check finite trajectories of central Algorithms 1 and 3, not convergence rates, runtime, random-permutation distribution, importance resampling or Shuffle-Once. Fixed permutations are conditioned random realizations, not a replacement sampling algorithm. The specified ProxRR stepsizes are valid inputs to Algorithm 1 and do not assert fidelity to the optional theorem schedule in Eq.(11). Unequal client sizes are explicitly allowed by Algorithm 3 even though subsequent convergence statements simplify to equal sizes. Quadratic losses are synthetic instances of the paper's general smooth convex objective; the second case additionally matches its empirical loss family. No attempt is made to infer undocumented benchmark choices.

To reproduce: run `/tmp/optirepro-paper-judge-20260915/bin/python derive_contract.py` from any directory. The builder deterministically rewrites this review, contract.json and SHA256SUMS and reads no implementation data.

## Bound hashes

PDF SHA256: `765342ddc320fe1b8f0507848a2ee818e9fd5080fa57d980bfa44acce44a7ae0`

Canonical contract digest: `334ce726e729eb2e30fff64ec705a5614147c3b316d9ebecdca7212eae2251ac`
