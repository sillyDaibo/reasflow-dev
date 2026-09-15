"""Source-only mutation preparation; no expected values or verdicts loaded."""
import ast
import hashlib
import json
from pathlib import Path
import shutil
import sys
ROOT=Path(__file__).resolve().parents[2]
OUT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'repo_judge'))
from src.judge.execution import _snapshot_digest,_workspace_snapshot
T=json.loads((OUT/'adapter_audit_targets.json').read_text())
mutations={
 'stratified-codex':[
 ('missing_loss_dual','strat_models/solvers.py','        u += r1\n','        u += 0.0 * r1\n','Suppress the loss-consensus scaled dual update; leave post-dual observation anchor unchanged.'),
 ('wrong_consensus_rhs','strat_models/solvers.py','        rhs = rho * (theta + u + v + w)\n','        rhs = 0.5 * rho * (theta + u + v + w)\n','Halve the consensus-system right side while retaining the original CG solver and trace anchor.')],
 'proxrr-codex':[
 ('wrong_prox_scale','rr_prox_fed/algorithms.py','                x = self.objective.regularizer(x, step * steps_per_epoch)\n','                x = self.objective.regularizer(x, step)\n','Remove epoch length from the proximal scale; retain original proximal function and observation prefix.'),
 ('wrong_inner_step','rr_prox_fed/algorithms.py','                x -= step * grad\n','                x -= 0.5 * step * grad\n','Halve each actual inner descent update without changing objective inputs or trace prefix.')],
 'beer-codex':[
 ('stale_gradient_tracker','beer_repro/algorithms.py','        self.v += self.gamma * ((self.w - np.eye(self.w.shape[0])) @ self.g) + gradients - self.grad_previous\n','        self.v += self.gamma * ((self.w - np.eye(self.w.shape[0])) @ self.g) + 0.0 * (gradients - self.grad_previous)\n','Suppress the gradient-difference correction while preserving original driver gradient locations, compressions and method-return observation.'),
 ('wrong_h_residual','beer_repro/algorithms.py','            qh[i] = compress(self.x[i] - self.h[i], self.compressor, self.compression_param, self.rng)\n','            qh[i] = compress(self.x[i], self.compressor, self.compression_param, self.rng)\n','Compress the raw iterate instead of the H residual. The public compressor remains input-only and cannot erase this defect.')]
}
records=[]
for target, changes in mutations.items():
 source=Path(T[target]['workspace']); before_snapshot=_workspace_snapshot(source)
 for change in [None]+changes:
  suffix='positive' if change is None else change[0]
  control_id=target+'-'+suffix
  dest=OUT/'controls'/control_id/'workspace'
  if dest.exists(): raise RuntimeError('Refuse overwrite: '+str(dest))
  dest.parent.mkdir(parents=True,exist_ok=True)
  shutil.copytree(source,dest)
  mutation=None
  if change:
   _,relative,before,after,reason=change
   path=dest/relative; text=path.read_text(); assert text.count(before)==1,(target,relative)
   path.write_text(text.replace(before,after)); ast.parse(path.read_text())
   mutation=dict(path=relative,before=before,after=after,reason=reason)
  copied=_workspace_snapshot(dest)
  modified=sorted(p for p in before_snapshot if copied.get(p)!=before_snapshot[p])
  assert set(copied)==set(before_snapshot)
  assert modified==([] if change is None else [change[1]])
  records.append(dict(id=control_id,base_target=target,workspace=str(dest),mutation=mutation,
   expected_numeric_outcome='match' if change is None else 'mismatch',
   expectation_basis='Prospective control expectation from intentional source mutation; no hidden expected values or verdicts consulted.',
   original_workspace=str(source),original_workspace_digest=_snapshot_digest(before_snapshot),workspace_digest=_snapshot_digest(copied),
   adapter=T[target]['adapter'],bindings=T[target]['bindings'],public=T[target]['public']))
 assert _workspace_snapshot(source)==before_snapshot
(OUT/'controls/manifest.json').write_text(json.dumps({'schema_version':'optirepro.mutation_controls.v1','controls':records},ensure_ascii=False,indent=2)+'\n')
print('Prepared',len(records),'controls')
