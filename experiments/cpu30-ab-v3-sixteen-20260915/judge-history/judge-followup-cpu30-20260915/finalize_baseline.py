"""Assemble all 16 paper pairs, preserving unsuccessful earlier attempts."""
from collections import Counter,defaultdict
from pathlib import Path
import hashlib,json,sys
ROOT=Path(__file__).resolve().parents[2];REPORT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'repo_judge'))
from src.judge.execution import _workspace_snapshot,_snapshot_digest
from src.judge.paper_contract import contract_digest
from src.judge.review_records import json_digest,validate_paper_review,validate_adapter_review

def main():
 targets=json.loads((REPORT/'TARGETS.json').read_text());by_target=defaultdict(list);all_attempts=[];batches=[]
 for path in sorted((REPORT/'validation').glob('*/summary.json')):
  batch=json.loads(path.read_text());assert batch['code_unchanged'],path
  hashes=json.loads((path.parent/'CODE_SHA256.json').read_text())
  for relative,digest in hashes.items(): assert hashlib.sha256((ROOT/relative).read_bytes()).hexdigest()==digest,relative
  batches.append(str(path))
  for row in batch['rows']:
   row={**row,'batch_summary':str(path)};by_target[row['target']].append(row);all_attempts.append(row)
 final=[];versions=[]
 for t in targets:
  name=t['target'];runs=by_target[name]
  assert len(runs)>=2,('not completed',name)
  latest=runs[-1]['batch_summary'];selected=[r for r in runs if r['batch_summary']==latest]
  assert len(selected)==2 and {r['repeat'] for r in selected}=={1,2},name
  assert all(r['source_unchanged'] and not r['direct_model_api_used'] for r in selected),name
  assert len({r['comparison_digest'] for r in selected})==1,('numeric instability',name)
  assert len({json.dumps(r['assessment'],sort_keys=True) for r in selected})==1,('assessment instability',name)
  assert all(r['status'] not in {'ENVIRONMENT_FAILED','RUN_FAILED'} for r in selected),('unresolved execution failure',name)
  workspace=Path(t['workspace']);assert _snapshot_digest(_workspace_snapshot(workspace))==t['workspace_digest'],name
  contract=json.loads(Path(t['contract_path']).read_text());paper_review=json.loads(Path(t['paper_review_path']).read_text())
  validate_paper_review(paper_review,contract)
  public=json.loads(Path(t['public_path']).read_text());adapter=Path(t['adapter_path']);bindings=json.loads(Path(t['bindings_path']).read_text())
  for b in bindings:b['path']=str((workspace/b['path']).resolve().relative_to(workspace.resolve()))
  review=json.loads(Path(t['adapter_review_path']).read_text())
  validate_adapter_review(review,public=public,adapter_sha256=hashlib.sha256(adapter.read_bytes()).hexdigest(),workspace_digest=t['workspace_digest'],bindings=bindings)
  assert paper_review['decision']==review['decision']=='approved'
  for row in selected:
   result=json.loads(Path(row['result']).read_text());frozen=Path(row['result']).parent/'frozen'
   assert result['contract_digest']==contract_digest(contract)
   assert json.loads((frozen/'paper_review.json').read_text())==paper_review
   assert json.loads((frozen/'adapter_review.json').read_text())==review
   assert (frozen/'adapter.py').read_bytes()==adapter.read_bytes()
  versions.append({'target':name,'workspace_digest':t['workspace_digest'],'contract_digest':contract_digest(contract),
                   'paper_review_sha256':hashlib.sha256(Path(t['paper_review_path']).read_bytes()).hexdigest(),
                   'adapter_sha256':hashlib.sha256(adapter.read_bytes()).hexdigest(),
                   'adapter_review_sha256':hashlib.sha256(Path(t['adapter_review_path']).read_bytes()).hexdigest(),
                   'environment_actions_sha256':hashlib.sha256(Path(t['environment_actions_path']).read_bytes()).hexdigest() if Path(t['environment_actions_path']).is_file() else None})
  final.extend(selected)
 assert len(final)==64 and len({r['paper_id'] for r in final})==16
 representatives={r['target']:r for r in final if r['repeat']==1}
 counts=Counter(r['status'] for r in representatives.values())
 eligible=sum(r['assessment']['acceptance']=='eligible_on_tested_scope' for r in representatives.values())
 incomplete=sum(r['assessment']['coverage']!='complete' for r in representatives.values())
 partial_diffs=sum(r['status']=='INCONCLUSIVE' and r['assessment']['numeric_mismatches']>0 for r in representatives.values())
 summary={'scope':'16 matched historical CPU30 papers, 32 unchanged workspaces','paper_count':16,'workspace_count':32,
          'final_evaluations':64,'total_evaluation_attempts':len(all_attempts),'eligible_on_tested_scope':eligible,
          'status_counts':dict(counts),'incomplete_workspaces':incomplete,'incomplete_with_numeric_differences':partial_diffs,
          'all_repeats_identical':True,'original_workspaces_unchanged':True,'paper_and_adapter_reviews_bound':True,
          'direct_model_api_used':False,'rows':final,'all_attempts':all_attempts,'batches':batches}
 (REPORT/'FINAL_SUMMARY.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2))
 (REPORT/'FINAL_ARTIFACT_VERSIONS.json').write_text(json.dumps(versions,ensure_ascii=False,indent=2))
 old=json.loads((ROOT/'reports/judge-cpu30-sixteen-20260915/FINAL_SUMMARY.json').read_text())
 prior={r['target']:r for r in old['rows'] if r['repeat']==1}
 for target,row in representatives.items():
  prev=prior[target]
  for key in ('status','reason_code','comparison_digest'):
   assert row[key]==prev[key],('baseline changed',target,key)
  for key,value in prev['assessment'].items():
   assert row['assessment'][key]==value,('existing assessment changed',target,key)
 summary['baseline_verdicts_and_numeric_comparisons_unchanged']=True
 (REPORT/'FINAL_SUMMARY.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2))
 print(json.dumps({k:v for k,v in summary.items() if k not in {'rows','all_attempts','batches'}},ensure_ascii=False,indent=2))
if __name__=='__main__':main()
