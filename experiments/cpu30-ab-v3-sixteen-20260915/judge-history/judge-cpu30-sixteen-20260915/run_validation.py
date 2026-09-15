"""Replay frozen paper-only experiments on selected matched CPU30 workspaces."""
import argparse
import asyncio
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import sys
import time
ROOT=Path(__file__).resolve().parents[2]
REPORT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'repo_judge'))
from src.judge.execution import execute_algorithm,_workspace_snapshot,_snapshot_digest
from src.judge.review_records import json_digest

def main():
 p=argparse.ArgumentParser()
 p.add_argument('--papers',nargs='+')
 p.add_argument('--targets',nargs='+')
 p.add_argument('--previous',action='store_true')
 p.add_argument('--repeats',type=int,default=2)
 p.add_argument('--workers',type=int,default=4)
 args=p.parse_args()
 targets=json.loads((REPORT/'TARGETS.json').read_text())
 if args.papers: targets=[t for t in targets if t['paper_id'] in args.papers]
 if args.targets: targets=[t for t in targets if t['target'] in args.targets]
 if args.previous: targets=[t for t in targets if t['previously_tested']]
 if not targets: raise ValueError('No selected targets')
 for t in targets:
  for k in ['paper_path','contract_path','paper_review_path']:
   if not Path(t[k]).is_file(): raise ValueError(f'{t["target"]}: missing {k}')
  status=Path(t['adapter_path']).parent/'status.json'
  blocked=status.is_file() and json.loads(status.read_text()).get('status')=='blocked'
  if not blocked:
   for k in ['adapter_path','bindings_path','adapter_review_path']:
    if not Path(t[k]).is_file(): raise ValueError(f'{t["target"]}: missing {k}')
   if not t['previously_tested'] and not Path(t['environment_actions_path']).is_file():
    raise ValueError(f'{t["target"]}: missing explicit environment actions')
 stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
 out=REPORT/'validation'/stamp;out.mkdir(parents=True)
 code_paths=[ROOT/'repo_judge/src/judge'/f'{n}.py' for n in ['algorithm_pipeline','paper_contract','review_records','algorithm_assessment','execution']]
 code_paths += [ROOT/'repo_judge/run_execution_judge.py',ROOT/'repo_judge/prepare_algorithm_judge.py',Path(__file__)]
 hashes={str(path.relative_to(ROOT)):hashlib.sha256(path.read_bytes()).hexdigest() for path in code_paths}
 (out/'CODE_SHA256.json').write_text(json.dumps(hashes,indent=2))
 def run(t):
  workspace=Path(t['workspace']);before=_snapshot_digest(_workspace_snapshot(workspace))
  if before != t['workspace_digest']: raise ValueError('Historical workspace changed before testing: '+t['target'])
  status_path=Path(t['adapter_path']).parent/'status.json'
  state=json.loads(status_path.read_text()) if status_path.is_file() else {}
  if state.get('status')=='blocked': adapter=state
  else: adapter={'path':t['adapter_path'],'bindings':json.loads(Path(t['bindings_path']).read_text())}
  actions_file=Path(t['environment_actions_path'])
  if actions_file.is_file(): actions=json.loads(actions_file.read_text())
  else:
   actions=[{'kind':'install_package','package':'numpy','reason':'Original source imports numpy','source':'source imports'}]
   if t['target']=='2212.02387-reasflow': actions.append({'kind':'install_package','package':'scikit-learn','reason':'Original data module imports sklearn','source':'src/dream_reproduction/data.py:8'})
  rows=[]
  for repeat in range(1,args.repeats+1):
   spec={k:t[k] for k in ['paper_path','contract_path','paper_review_path','adapter_review_path']}
   spec.update(evaluation_id=f'paper16-{repeat}',paper_id=t['paper_id'],adapter=adapter,environment_actions=actions,timeout_seconds=240)
   sp=out/f'{t["target"]}-{repeat}.spec.json';sp.write_text(json.dumps(spec,ensure_ascii=False,indent=2))
   start=time.monotonic()
   result=asyncio.run(execute_algorithm(str(workspace),str(sp),run_root=str(out/t['target'])))
   assessment=result['assessment']
   result_path=Path(result['algorithm_dir'])/'result.json'
   manifest=json.loads((result_path.parents[1]/'EVALUATION_MANIFEST.json').read_text())
   row={'target':t['target'],'paper_id':t['paper_id'],'variant':t['variant'],'repeat':repeat,
        'status':result['status'],'reason_code':result['reason_code'],'reason':result['reason'],
        'assessment':assessment,'result':str(result_path),'elapsed_seconds':time.monotonic()-start,
        'comparison_digest':json_digest(result.get('comparison',{})),
        'source_unchanged':before==_snapshot_digest(_workspace_snapshot(workspace)),
        'direct_model_api_used':bool(manifest['algorithm'].get('model_stages'))}
   rows.append(row)
   (out/f'{t["target"]}-{repeat}.row.json').write_text(json.dumps(row,ensure_ascii=False,indent=2))
   print(t['target'],repeat,row['status'],row['reason_code'],assessment['acceptance'],assessment['numeric_mismatches'],flush=True)
  return rows
 with ThreadPoolExecutor(max_workers=args.workers) as pool:
  rows=[r for group in pool.map(run,targets) for r in group]
 summary={'created_at':stamp,'rows':rows,'code_unchanged':all(hashlib.sha256((ROOT/path).read_bytes()).hexdigest()==sha for path,sha in hashes.items()),
          'scope':'Matched historical CPU30 workspaces; frozen paper-only expectations, independent reviews and original algorithm calls. Finite experiments only.'}
 (out/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2))
 print('SUMMARY',out/'summary.json',flush=True)
if __name__=='__main__':main()
