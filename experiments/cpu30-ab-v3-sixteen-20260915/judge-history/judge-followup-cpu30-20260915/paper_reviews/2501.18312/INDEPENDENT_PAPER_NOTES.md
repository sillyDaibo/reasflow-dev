# Independent paper-only notes: 2501.18312 Algorithm 3

Reviewer: adapter16_c. Written before seeing the new finite contract or its author's derivation program.

## Information boundary and evidence

I have not read this paper's reproduction workspace, adapter, prior contract/review, run outputs, private expected trajectories, or actual Judge results. Earlier tasks involved other paper IDs only. Sources for these notes are the original `datasets/benchmarks/cpu30_v1/input/2501.18312/paper.pdf` and the review-format instructions. PDF pages 11, 17, 18, 19 and 20 were rendered and visually inspected; adjacent definitions on pages 6-9 were read from extracted original text. The discussion below is an independent reconstruction, not an implementation assessment.

## Local WB oracle and PPS

Page 19 Eq. (9) poses a semi-discrete entropy-regularized Wasserstein barycenter, with continuous source distributions having densities, a finite target support, and a connected undirected communication graph. For a strictly positive entropy coefficient gamma, page 20 Lemma 3 gives the local conjugate-gradient sample

`p_l(v,s) = exp((v_l-c(z_l,s))/gamma) / sum_j exp((v_j-c(z_j,s))/gamma)`.

The numerator and denominator must use the same sampled source point. The printed denominator uses `Y` where the preceding formula uses `x`; the expectation and softmax normalization identify this as the same local random sample, rather than an independently sampled denominator. Every p is a positive simplex vector. Subtracting a common maximum from the logits is an algebraically equivalent stable evaluation, not an algorithm change.

For r independent source samples, page 6 defines the mini-batch mean `q = (1/r) sum_a p(v,s_a)`. PPS Eq. (1), pages 6-7, quantizes the mini-batch mean, not each sample before averaging. General PPS decomposes q into positive/negative parts and independently samples M categorical indices from each nonzero part. In this WB specialization q is in the simplex: positive mass is exactly one, negative mass is zero, so the transmitted vector is

`G = (1/M) sum_b e_{k_b}`, with `k_b ~ Categorical(q)` independently conditional on q.

Zero negative mass contributes the zero vector and must not require dividing by zero or sampling an undefined negative distribution. Repeated sampled indices produce counts, not deduplicated support. Node-specific samplers are independent; a finite test may condition on explicit source samples and categorical uniform draws. Page 7 explicitly permits representing categorical random inputs as uniforms on [0,1] transformed using the current probabilities. A valid contract should state the inverse-CDF convention and choose supplied uniforms away from cumulative-probability boundaries. Fixed labels can also condition on a realization if they have positive probability, but testing the CDF from supplied uniforms more directly tests the stated quantization.

The negative sign of graph-coupled components does not mean local WB p has a negative branch. PPS happens locally on p/q before the Laplacian mixes messages.

## Algorithm 3 state recurrence, independently transcribed from page 17

Use matrices with one node per row and support coordinates per column. The following identifies `H_t` with the graph mixing of all locally quantized messages; the diagonal issue discussed below must be resolved explicitly by the contract.

- Initial oracle evaluation: `mu_0=0`; evaluate the local mini-batches and quantize them into `G_0`.
- Set `H_0=W G_0`, `lambda_0=-(alpha_0/beta_0) H_0`, and `A_0=alpha_0`.
- For each transition `t=0,...,T-1`:
  1. `A_(t+1)=A_t+alpha_(t+1)` and `tau_t=alpha_(t+1)/A_(t+1)`.
  2. `z_t=-(1/beta_t) sum_(k=0)^t alpha_k H_k`.
  3. `mu_(t+1)=tau_t z_t+(1-tau_t)lambda_t`.
  4. Evaluate fresh local sample softmaxes at `mu_(t+1)`, form the mini-batch means, and apply PPS to obtain `G_(t+1)`; communicate and form `H_(t+1)=W G_(t+1)`.
  5. `hat_mu_(t+1)=z_t-(alpha_(t+1)/beta_t) H_(t+1)`.
  6. `lambda_(t+1)=tau_t hat_mu_(t+1)+(1-tau_t)lambda_t`.

The z step uses the entire alpha-weighted history through time t. The new message enters the separate hat_mu correction and will enter the history in the next transition. Both z_t and hat_mu_(t+1) divide by beta_t, not beta_(t+1). Initialization already makes one oracle call; T transitions require T+1 oracle batches. Each transition first computes all new node messages from the same precommunication state, then updates every node. Sequential in-place node updates that mix old/new communication states are not stated by the algorithm.

For timing, an observation named `mu` at transition step j=t+1 should mean mu_(t+1); `z` should mean z_t; accepted `lambda` should mean lambda_(t+1). Initial lambda_0 is a separate state and is not the first completed loop update.

## Paper ambiguities which a new finite test must not hide

### Laplacian diagonal

Page 17 writes sums over `j E i` although pages 6 and 17 define E as neighbors in an undirected graph, with no explicit self-neighbor convention. A literal open-neighbor sum drops W_ii and is not the full Laplacian action. Page 18 explicitly derives the update identity containing `W x(lambda)` and defines W as the graph Laplacian, with its zero eigenvalue and consensus nullspace. Thus full `WG` has direct supporting evidence on page 18. A contract should explicitly cite this identity and say that the locally available diagonal term is included, rather than quietly treating the page-17 neighbor notation as unambiguous. Omitting the diagonal changes the finite iterates in general. No implementation evidence is needed or appropriate to decide the interpretation.

### Missing primal initialization and missing restoration time index

Page 17 does not initialize x_0. Its restoration line reads

`x_(t+1)^i = alpha_(t+1)/A_(t+1) * x^i(mu_i,xi_i) + A_t/A_(t+1) * x_t^i`,

but the call arguments have no time indices. Both defects affect a requested finite primal trajectory. Page 11 Algorithm 2 supplies an explicit weighted sum over all oracle points 0 through t+1; pages 8-9 Eqs. (5)-(6) identify primal restoration with a conjugate gradient. These support a natural reconstruction, but Algorithm 3 alone does not literally specify x_0 or whether the restoration call uses a particular mini-batch sample/average. A main contract can avoid relying on this issue by measuring local p/q, G, graph mixed messages, z, mu, hat_mu and lambda without requiring the accumulated primal x. It should not label q as the algorithm's accumulated barycenter x.

### Distributed coordinate scaling by m

Page 18 Eq. (8) uses the average objective and conjugates evaluated at `m(sqrt(W) lambda_bold)^i`, then states the plain variable as `lambda=sqrt(W)lambda_bold`. Page 19's WB specialization instead states `lambda=m[sqrt(W)lambda_bold]`. A direct derivative check gives, for `D(bold_lambda)=(1/m) sum_i phi_i(m S bold_lambda)` with S=sqrt(W),

`grad D = S p(m S bold_lambda)`.

Consequently the update in coordinate `v=m S bold_lambda` carries `m W p(v)`, whereas in coordinate `u=S bold_lambda` it carries `W p(m u)`. Page 17 displays `W G` and a local oracle at the plain mu without spelling out this distinction. A finite contract must define exactly which coordinate feeds the softmax and whether any m is absorbed into local conjugates, W, or beta. Testing page-17 recurrences with an explicitly supplied local oracle and W is a well-defined finite specialization; it should not simultaneously claim that every printed average-objective coordinate formula on pages 18-19 has been uniquely reconciled. Do not change numerical scale based on source implementation.

### Batch-size indexing and coefficient schedules

Page 17's initialization refers to r_t/M_t before defining t, and the call labeled t+1 uses r_t/M_t. Constant r and M avoid any trajectory ambiguity. If changing schedules are tested, the exact call-to-budget mapping must be declared and justified.

Alpha, beta, r and M are inputs; page 17 does not supply a unique default schedule. Page 11 states sufficient coefficient conditions, including alpha_0 in (0,1], beta_t greater than L and nondecreasing, and an alpha/beta inequality whose printed sum index is itself inconsistent. A finite recurrence check can supply positive schedules directly but should separately state whether it claims theorem-level conditions. Conservative constant beta and simple alpha are easier to justify; the finite experiment is not a proof of the communication/convergence theorem.

## Scope and checks for the coming independent recomputation

A useful nontrivial finite test needs multiple nodes, nonidentical local probability means, a connected graph with actual off-diagonal communication, M finite, and several transitions. Verify that at least one PPS output differs from its prequantized q, categorical choices depend on the q CDF, and graph mixing is not identically zero. Check source-sample and quantization axes separately. For continuous-source WB, a fixed conditional list of samples from supported locations is legitimate; replacing the distribution with a discrete empirical source should be labeled as a separate specialization.

With the full Laplacian interpretation, row sums of p/q/G are one, coordinate sums of WG are zero, and summing WG over nodes gives zero. Initialization and subsequent lambda/mu/z remain in the node-consensus orthogonal subspace up to roundoff. These are useful internal checks independent of any expected answer. The contract's raw state comparisons must still come from an independent recurrence, not merely these invariants.

These tests can establish finite arithmetic behavior for the chosen interpretation and random realization. They do not establish barycenter optimality, asymptotic consensus, the stated concentration lemma, communication complexity, support-size independence, or performance on Gaussian/MNIST examples. No numerical correctness verdict is issued before reading and independently recomputing the new contract.
