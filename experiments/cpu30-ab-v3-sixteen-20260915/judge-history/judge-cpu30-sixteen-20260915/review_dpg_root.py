"""Record root's source/public-input audit, completed before numerical comparison."""
import json,hashlib,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];REPORT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'repo_judge'))
from src.judge.execution import _workspace_snapshot,_snapshot_digest
from src.judge.review_records import json_digest,validate_adapter_review
for target in json.loads((REPORT/'PUBLIC_TARGETS.json').read_text()):
 if target['paper_id']!='2111.03820':continue
 adapter=Path(target['adapter_path']);workspace=Path(target['workspace'])
 public=json.loads(Path(target['public_path']).read_text());bindings=json.loads(Path(target['bindings_path']).read_text())
 for b in bindings:b['path']=str((workspace/b['path']).resolve().relative_to(workspace.resolve()))
 variant=target['variant']
 notes=['Reviewed only public experiment inputs, adapter and original algorithms.py; private expected arrays, author derivations and numerical Judge outputs were not read for this audit.',
 'Both public cases are 1D, two agents, two samples, three epochs. Signed features with y=+1 exactly represent the stated logistic sample functions; original gradients and proximal maps are retained.',
 'Initial state is assigned once via a source-line trace after allocation and before any algorithm update. No later state is overwritten.',
 'The original RNG is called once per execution; two permutation calls per epoch consume the declared shared order. This checks conditional trajectories, not the random distribution.',
 'The public mixing matrices are powers of the first A. Original source computes those powers; the adapter does not replace consensus.',
 'inner_x contains copied actual pre-gradient arguments plus the original local-epoch endpoint, arranged by step and agent; inner_gradient, consensus_v and x_next are copied original inputs/outputs. No update recurrence is reconstructed.',
 'Only dataset loading and prescribed initialization/random input are supplied. Original objective/gradient, normalization, dtype, consensus and prox are retained; unobserved metrics are allowed to run.']
 notes.append('Codex original _sample_gradient exponential clipping remains unchanged; run_method, _mix and _soft_threshold execute directly.' if variant=='codex' else 'ReasFlow gradient logging filters only original _local_stochastic_epoch callers. Its original len(idx)/n inner-step scaling remains unchanged, as do original _consensus_matrix and _prox_consensus.')
 record={'schema_version':'optirepro.adapter_review.v1','reviewer_id':'root_independent_source_audit','basis':'public_inputs_and_source_only',
 'decision':'approved','summary':'Faithful DPG-RR driver, original logistic/consensus/prox and actual multi-step observations for the declared public cases.',
 'scope_notes':notes,'substitutions':[
 {'symbol':'np.random.default_rng','role':'problem_input','reason':'Supply the publicly fixed shared sample permutation per epoch; original RNG call placement retained.'},
 {'symbol':'run_method initialization trace','role':'problem_input','reason':'Insert public per-agent x0 immediately after original allocation, once only.'},
 {'symbol':'gradient/mix/prox wrappers and array arrangement','role':'observation','reason':'Call originals and copy actual arguments/returns; no algorithm update replacement.'}],
 'public_digest':json_digest(public),'adapter_sha256':hashlib.sha256(adapter.read_bytes()).hexdigest(),
 'workspace_digest':_snapshot_digest(_workspace_snapshot(workspace)),'bindings_digest':json_digest(bindings)}
 validate_adapter_review(record,public=public,adapter_sha256=record['adapter_sha256'],workspace_digest=record['workspace_digest'],bindings=bindings)
 Path(target['adapter_review_path']).write_text(json.dumps(record,ensure_ascii=False,indent=2))
 (adapter.parent/'INDEPENDENT_REVIEW.md').write_text('# Independent DPG-RR adapter review\n\nReviewer: root, before private numerical comparison. Decision: approved for faithful observation only.\n\n'+'\n\n'.join(notes)+'\n')
 print(target['target'],record['decision'])
