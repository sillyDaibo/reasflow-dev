"""Independent source-only adapter review records; no private contracts loaded."""
import hashlib,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]; OUT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'repo_judge'))
from src.judge.execution import _snapshot_digest,_workspace_snapshot
T=json.loads((OUT/'adapter_audit_targets.json').read_text())
def sub(symbol,reason,role='problem_input'):return dict(symbol=symbol,role=role,reason=reason)
common=[
 'Approval means faithful execution/observation within the stated public-input scope, not agreement with the paper or correctness of the algorithm.',
 'Reviewed the redacted public cases, adapter source, bindings and original CPU30 source only; no private contract, expected-value array, derivation script, prior adapter review or prior verdict was consulted.',
 'Source and adapter hashes bind this static review. Execution success and numerical agreement require the separate runtime/provenance/comparison stage.',
 'Synthetic problem callbacks cannot validate the displaced original objective/data/compression primitives. They must not be described as a full original end-to-end application reproduction.',
]
R={}
for variant in ['codex','reasflow']:
 R['rsa-'+variant]=dict(
 summary='Approved for genuine original RSA updates on supplied quadratic objectives and prescribed Byzantine messages; source normalization and update ordering remain observable.',
 notes=[
  'Input mapping: public initial master/regular-worker vectors, penalty norm, lambda and Byzantine message arrays map to original state/arguments; master center must be zero and weight_decay/l2 is 1.',
  'Original norm_subgradient and '+('rsa_step' if variant=='codex' else 'run_training')+' execute unchanged. The source divides local objective gradients by total worker count and forms master penalties using transmitted post-worker-update models; the adapter leaves both choices intact.',
  'Observation timing: objective-gradient and norm-return copies are taken during the real step; penalty is read from its original local; completed master/workers are copied after updates. Master regularizer gradient is derived solely from the original pre-update operand and coefficient, never fed back.',
  ('Every requested alpha is supplied through rsa_step API, retaining original float64 state arrays.' if variant=='codex' else 'The original float32 10-class allocation is retained and vectors occupy row zero. Initialization injection happens once before the loop; the fixed alpha0/sqrt(step+1) schedule is not overridden. Only the matching prefix executes, and subsequent requested observations are explicitly blocked.'),
  'No claim is made about original softmax objective or attack-generator correctness; prescribed attacks and quadratic gradient replace these problem boundaries.'
 ],substitutions=[sub('softmax_gradient','Return supplied quadratic objective gradients at the exact source-requested point; original driver normalization remains.'),sub('attack_message' if variant=='codex' else '_attack_message','Supply the external Byzantine sender vectors; ReasFlow honest-sender helper remains original.'),sub('sys.settrace','Copy original norm return values and update frame locals; no iterative state overwrite.', 'observation')]+([] if variant=='codex' else [sub('run_training initial theta/local buffers','One-time insertion of supplied initial values, preserving float32 allocation and zero unused coordinates.')]))
for variant in ['codex','reasflow']:
 R['dream-'+variant]=dict(
 summary='Approved as a partial original DREAM trajectory adapter; missing output selection and unavailable states remain blocked rather than synthesized.',
 notes=[
  'Input mapping: public coefficients define a one-x/one-y quadratic saddle objective; initial buffers are resized and assigned once before gradient/tracker initialization. Public eta/gamma, batch sizes, probabilities and mixing counts use configuration fields.',
  'The original run_algorithm, '+('_gradients' if variant=='codex' else '_run_dream/_compute_gradients')+' and fast_mix execute unchanged. Every original FastMix call checks that its actual matrix equals public W; only the ring-representable supplied matrices are supported.',
  'Synthetic gradient averages precisely the indices the source requests; it does not implement gating, estimator recursion, q scaling, or mixing.',
  'Random input mapping is based on source generator identity and call order: node 0 first scalar draw is refresh, later/node-specific draws are activity, and supplied sample indices are returned with batch-size checks. This is narrowly bound to the inspected source call structure.',
  ('Native DREAM makes one node-0 activity decision for all nodes; the adapter preserves this source behavior rather than injecting independent per-node control. It projects after mixing, so requested pre-mixing projected state is unavailable.' if variant=='codex' else 'ReasFlow retains its node-local activity decisions, original projection-before-y-mixing, estimator update ordering and original FastMix recurrence.'),
  'Observation timing: _record is intercepted at entry after state assignment; state arrays are copied. pre_projection and tracker_input are copies of actual FastMix inputs; ReasFlow projected rows are actual projection I/O, not recomputed state.',
  'Original output only contains metric histories. The adapter never invents output_candidates/x_out and intentionally returns blocked for missing output observations. It does not consume output_draw_index because there is no source output-selection operation.',
  'Original saddle objective, simplex projection and RNG are outside the verified implementation scope; this approves core-driver observation with the public objective/domain/randomness, not those replaced primitives.'
 ],substitutions=[sub('local_gradient' if variant=='codex' else 'local_gradients','Public synthetic component objective at source-requested samples and points.'),sub('project_simplex_rows' if variant=='codex' else 'project_simplex','Public y feasible interval projection, leaving source placement of projection intact.'),sub('numpy.random.default_rng','Supply prescribed random realizations through only the source-consumed RNG API.'),sub('_initial_state' if variant=='codex' else '_fresh_state','Return-event buffer edit only for public dimension and initial state before driver use.'),sub('sys.settrace','Read original FastMix inputs and state at _record; projection I/O copied as observed.', 'observation')])
for variant in ['codex','reasflow']:
 R['stratified-'+variant]=dict(
 summary='Approved for complete original ADMM iterations with public proximal-problem inputs and unchanged consensus/dual update code.',
 notes=[
  'Input mapping: supplied L becomes the original sparse graph/operator or Laplacian API; lambda maps to rho=1/lambda, state shapes are K by parameter_dimension, and default zero initialization implements the public start.',
  'Quadratic Q,b are mapped to sum-squares sufficient statistics XtX=Q/2 and XtY=-b/2. Public Poisson counts/sums are passed to the original Poisson prox. This changes input representation without implementing ADMM iterates.',
  ('ridge_prox, ridge_regularizer_prox, poisson_prox, _solve_system and fit_admm are original calls. Only the absent L1 primitive is supplied by an adapter callback.' if variant=='codex' else 'fit_stratified_model, _call_prox, original sum_squares_loss/poisson_loss prox and original sum_squares_reg/L1_reg prox execute. rho adaptation is disabled through supported tau/min/max arguments.'),
  'The core loss/regularizer/consensus/dual update order and original CG tolerance/iteration cap remain unchanged. No linear-system inverse, consensus solve or next state is generated by the adapter.',
  'Observation timing: exact unique source line immediately after both dual updates, before primal-norm calculation. The five original arrays are copied with one-based completed iteration labels; missing/early-stop states are blocked.',
  'Setting abs_tol=rel_tol=0 uses the original stopping API; an exactly converged zero-residual source could still stop early. Original CG and proximal numerical limitations remain visible.',
  ('The L1 callback is a declared public problem input and excludes original L1-primitive verification, since that source has no such primitive. Core ADMM mutations are not masked.' if variant=='codex' else 'The synthetic sufficient-statistic cache excludes raw-data setup/preprocessing verification. Any difference in original proximal scaling remains observable.')
 ],substitutions=[sub('loss_prox callback','Translate public quadratic/Poisson data into existing original prox interfaces; wrapper calls original primitive.'),sub('regularizer_prox callback','Supply public coefficient to original regularizer prox'+('; implement public L1 prox only where no primitive exists.' if variant=='codex' else '.')),sub('sys.settrace','Read five original completed-iteration states after both dual updates; never assign them.', 'observation')])
for variant in ['codex','reasflow']:
 R['proxrr-'+variant]=dict(
 summary='Approved for original ProxRR/FedRR driver and proximal updates with public objective/order inputs; original logistic gradients remain covered.',
 notes=[
  'Input mapping: x0, public regularizer coefficients, epoch/client orders and sample counts are supplied through original driver APIs. The RNG checks permutations against each actual source request.',
  'For per-epoch gamma the adapter executes a one-epoch original ProxRR driver per public epoch, carrying only its returned x into the next API call. This is scoped to the source state consisting of x and the public schedule/orders, with decay/importance sampling disabled by defaults.',
  'The public quadratic gradient is an input oracle. It preserves source-requested sample index, current point and requested normalization. The logistic case instantiates and calls the original logistic loss class, leaving its treatment of L2 observable.',
  ('ProxRR.run, ElasticNetLogistic.gradient, ProximalOperator.__call__, and FedRR.run are original. FedRR local objective factory is replaced; its global logistic object is only unobserved logging.' if variant=='codex' else 'prox_rr, original LogisticElasticNet.gradient_batch, original elastic_net_prox, fed_rr and _run are original. FedRR _partition and local loss construction supply public unequal client sizes; original rounding of local_n and server prox scale remain unchanged.'),
  'Observation timing uses the next line/return trace event after original x -= or z -= to copy true inner iterates; original proximal assignment is observed after execution; local endpoints and equal-weight aggregation are captured at their actual source statements.',
  'This does not validate original quadratic/data factory behavior displaced by QuadraticInput. In ReasFlow the synthetic oracle does not inherit the original logistic extra-L2 gradient behavior; the distinct logistic public case retains coverage of that implementation.',
  'FedRR core local update, aggregation and regularization are untouched. Original proximal n scaling and server scaling can therefore fail independently of adapter approval.'
 ],substitutions=[sub('QuadraticInput.gradient/gradient_batch/value','Public synthetic loss oracle and unobserved objective logging; original proximal map retained.'),sub('numpy.random.default_rng','Public epoch/client permutation input only, with exact consumption checks.'),sub('_client_objective' if variant=='codex' else 'federated.LogisticElasticNet','Construct public quadratic local loss; no driver updates replaced.'),sub('sys.settrace','Observe actual completed gradient steps, aggregation and original proximal statements.', 'observation')]+([] if variant=='codex' else [sub('federated._partition','Supply the public unequal client partitions rather than a randomly repartitioned dataset.')]))
for variant in ['codex','reasflow']:
 R['beer-'+variant]=dict(
 summary='Approved for genuine original BEER control flow, gradient locations, compression residuals and observed X/H/V/G state.',
 notes=[
  'Input mapping: client labels encode objective identity, public diagonal quadratics provide pointwise full deterministic gradients, initial_common_point and W enter the original driver, and eta/gamma/iterations map directly to original arguments.',
  'The public compressor is implemented as an oracle because compression map is an explicit test input. It executes wherever the original driver calls compression; choice of residual/raw state and channel update is not rewritten.',
  ('Original runner.run_experiment, BEER.initialize and BEER.step execute. The runner computes the next-point gradient location and supplies it to the original step; the adapter never predicts that location. Initialization/method-return events copy row-major internal arrays transposed to public [dimension][client].' if variant=='codex' else 'Original run_decentralized executes unchanged with a model object. Initial x0 is copied once into the original float32 buffer before replication/gradients. Step 0 is captured before the original first x advance; step t is captured after v/gstate catch up and before the next x_new, giving the source staggered full-round cut.'),
  'State observations are copies only. Compression, tracking and descent state are never assigned by the adapter; public objective/compressor functions do not generate expected trajectories.',
  ('Original dataset loader, initial-point generator, topology constructor, logistic loss and accuracy are replaced at input/logging boundaries; run_experiment output goes into a temporary directory.' if variant=='codex' else 'The model gradient retains float32 output and source float32 state behavior. The source executes a further x/h half-round after the final observed complete-round cut; this adapter reports only the declared complete-round state, not that later return state.'),
  'Original data preprocessing, logistic objective, stochastic sampling and compressor implementation are outside this scope. Only driver use of the prescribed compressor, including per-client call placement/residual arguments, is verified.'
 ],substitutions=([sub('runner.load_a9a','Construct synthetic clients with public objective identities.'),sub('runner._initial_params','Public common initial point.'),sub('runner.mixing_matrix','Public W.'),sub('runner.logistic_loss_gradient','Public deterministic quadratic objective at the original runner-selected point.'),sub('runner.logistic_accuracy','Unobserved logging constant.'),sub('algorithms.compress','Public specified scale/top1 compressor.')]
 if variant=='codex' else [sub('SyntheticQuadratic model','Public deterministic objective and unobserved accuracy metadata.'),sub('core.compressor','Factory returns prescribed scale/top1 compressor.'),sub('run_decentralized x0 buffer','Public initial value injected once before replication, keeping original dtype.')])+[sub('sys.settrace','Copy original X/H/V/G at initialization and complete-round execution boundary.', 'observation')])

def canonical(value):return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()).hexdigest()
dir=OUT/'adapter_reviews';dir.mkdir(exist_ok=True)
for target,data in R.items():
 t=T[target]; workspace=Path(t['workspace']); bindings=json.loads(Path(t['bindings']).read_text())
 normalized=[dict(b,path=(workspace/b['path']).resolve().relative_to(workspace.resolve()).as_posix()) for b in bindings]
 value=dict(schema_version='optirepro.adapter_review.v1',reviewer_id='adapter_audit_controls',basis='public_inputs_and_source_only',decision='approved',summary=data['summary'],scope_notes=common+data['notes'],substitutions=data['substitutions'],public_digest=canonical(json.loads(Path(t['public']).read_text())),adapter_sha256=hashlib.sha256(Path(t['adapter']).read_bytes()).hexdigest(),workspace_digest=_snapshot_digest(_workspace_snapshot(workspace)),bindings_digest=canonical(normalized))
 (dir/(target+'.json')).write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n')
 md='# '+target+' independent adapter review\n\nDecision: **approved within declared scope**. '+data['summary']+'\n\n'
 md+='\n\n'.join(common+data['notes'])+'\n\n## Substitutions\n\n'
 md+='\n'.join('- `'+s['symbol']+'` ('+s['role']+'): '+s['reason'] for s in data['substitutions'])
 md+='\n\nNo core algorithm replacement identified. Approval does not assert numerical match.\n\n## Bound evidence\n\n'
 md+='\n'.join('- '+k+': `'+value[k]+'`' for k in ['public_digest','adapter_sha256','workspace_digest','bindings_digest'])+'\n'
 (dir/(target+'.md')).write_text(md)
print('Wrote',len(R),'independent reviews')
