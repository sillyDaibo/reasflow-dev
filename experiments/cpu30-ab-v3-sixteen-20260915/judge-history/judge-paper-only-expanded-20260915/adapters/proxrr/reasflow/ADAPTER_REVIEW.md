# Independent ProxRR/FedRR adapter review

Only `public/2102.06704/public_cases.json` and original implementation source files from this workspace were read. No private paper contract, derivation, review, expected results, original PDF, repository tests or experiment result data was read. These adapters do not compute or compare expected trajectories.

## Execution and input injection

The adapter reads `OPTIREPRO_WORKSPACE` and `OPTIREPRO_CASES`, imports the original Python package from that workspace, and emits one `OPTIREPRO_OBSERVATIONS={"cases":[...]}` line. It never writes to the workspace; smoke tests set `PYTHONDONTWRITEBYTECODE=1` and the adapter also disables bytecode writes.

The two ProxRR experiments invoke the complete original single-machine driver for one epoch at a time. Each public gamma enters the driver's existing scalar stepsize argument, each next x0 is the previous driver's returned x, and each epoch's RNG permutation is prescribed at the `np.random.default_rng` boundary. This exposes the public epoch-specific stepsizes using the driver's native one-epoch interface. It does not test any implementation-specific learning-rate decay policy. The actual original driver executes every inner gradient update and the entire epoch-end regularizer operation with its original scaling.

The quadratic case supplies an objective callback implementing the publicly specified component loss and gradient. This callback contains no optimization update. For logistic inputs the original native logistic objective and gradient execute, including any original additional terms. The quadratic callback uses the original elastic-net proximal operator; the adapter never reimplements a proximal map.

The federated experiment calls the original complete federated driver for all three rounds with the two public sample-count-specific clients. Client-local quadratic objective factories are the only objective boundary injections. All original local update loops, averaging, server prox scale and shrinkage operations remain unchanged. Permutations are supplied separately for every client and round. The optional local step argument is set to the public maximum client sample count, so the original implementation can process all real samples.

A `sys.settrace` callback observes selected original function statements immediately after execution. It copies local variables after each inner `x -= ...`/`z -= ...`, after appending a completed client, after original `np.mean`, and after original regularizer statements. Each reported vector is a state that existed in the original function; the adapter does not derive states from gradients or reconstruct means/updates. It never sets a profile hook; Python's `sys.setprofile` is separate from this trace hook. Existing trace hooks are restored after execution.

## Public-only smoke result

Smoke runs used `/tmp/optirepro-paper-judge-20260915/bin/python`. All three cases executed with no stderr or blocked case. The two ProxRR cases each supplied six observations; the FedRR case supplied twelve. Public observation coordinates/shapes and finite numeric output were checked; no numerical expected values were read or compared. Dependency packages were already available (NumPy 2.0.2, SciPy 1.13.1 where needed), so no environment installation occurred. `environment_actions.json` records source-grounded package requirements, explicitly noting this.

## Coverage limits

The adapter measures the original sequential component updates, original epoch-end regularizer, original complete local client passes, original server aggregation and original server regularization. External orchestration selects public epoch stepsizes; native automatic schedules are not tested. Data download, benchmark training, convergence, RNG distribution, speed, and reference solvers are not run. A callback changes the objective input when the public case is quadratic; it does not establish that the repository natively exposes a quadratic dataset model.

If execution or observation fails, the output identifies a blocked case and missing coordinates. No replacements for unavailable algorithm states are fabricated. These finite measurements must be compared by a separate party; the adapter makes no pass/fail assertion about algorithm correctness.

## Workspace-specific bindings

- `rr_prox_fed/methods.py:prox_rr` is the full single-machine driver. Native `losses.py:LogisticElasticNet.gradient_batch` and `elastic_net_prox` execute for the logistic case. The quadratic case supplies its public loss callback and still executes native `elastic_net_prox`.
- The native logistic gradient adds its stored l2 term; this behavior is retained with the public l2 coefficient. No compensating subtraction or modified coefficient is used.
- `rr_prox_fed/federated.py:fed_rr` calls its original `_run` driver for all rounds. The `_partition` boundary returns the prescribed public clients, and the module's local `LogisticElasticNet` construction is supplied a factory for the public quadratic functions.
- `_run` computes an integer-rounded mean client sample count for its prox scale. This source behavior is retained; the adapter does not replace it with the public mathematical ratio. All mean and proximal results are taken from the original execution.
- Only NumPy is required by these original modules.
