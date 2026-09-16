# Paper basis: 2306.05100

Only the supplied original PDF informed this contract. No reproduction implementation, adapter, output, historical assessment, or other report was read. Source SHA256 is recorded in contract.json.

## Source and algorithm

PDF p.7, Section 4, Algorithm 2 explicitly specifies the federated algorithm: corrected local operator update (line 4), communication of `x_hat - gamma/p * h` and uniform server average (lines 5-7), skipped communication (lines 8-9), and the control update `h + p/gamma*(x_next-x_hat)` (line 11). All signs and factors were checked on the rendered page. The surrounding text explains that the generic VIP operator can be instantiated as the deterministic GDA operator. PDF p.8 Assumption 4.1 concerns local quasi-strong monotonicity.

The selected operators are genuine two-dimensional strongly convex-concave saddle problems, with nonzero bilinear coupling and heterogeneous local objectives. Positive diagonal symmetric parts ensure strong monotonicity; full local operators remove gradient noise without removing the skip/communication randomness or control correction mechanism.

## Small experiments

Two four-update cases use opposite skip/communication order, supported fixed Bernoulli outcomes, and different saddle coefficients and nonzero initial control vectors whose sum is zero. Both begin from consensus. Public inputs specify the exact local objective/operator relationship, server topology, initialization, loop interpretation, and measurement timing. The printed inclusive loop `0,...,T` is resolved explicitly as `T=3`, four updates.

The independent standard-library script performs every operation with `fractions.Fraction`. The private derivation contains exact rational state traces; numeric JSON rounds once. Pre-update operators, provisional local points, post-update primal/control states, mean state, and cumulative communications are observed after each update. Tolerances `atol=rtol=1e-10` allow ordinary double precision accumulation and are many orders smaller than changes caused by a missing control correction or wrong branch.

Scope is Algorithm 2's deterministic full-operator specialization, not Algorithm 3/4 variance reduction, general proximal operators, or asymptotic communication-rate validation. No independent paper-review conclusion is asserted here.
