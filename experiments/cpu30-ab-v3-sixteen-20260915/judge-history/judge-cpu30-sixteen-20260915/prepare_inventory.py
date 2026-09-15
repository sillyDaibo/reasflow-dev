"""Inventory the 16 matched historical CPU30 pairs without inspecting source code."""
import importlib.util
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[2]
REPORT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'repo_judge'))
from src.judge.execution import _workspace_snapshot,_snapshot_digest
previous_path=ROOT/'reports/judge-paper-only-expanded-20260915/run_benchmark.py'
loader=importlib.util.spec_from_file_location('old',previous_path); old=importlib.util.module_from_spec(loader);loader.loader.exec_module(old)
old_targets={(t[1], 'codex' if 'Codex原生' in t[3] else 'reasflow'):t for t in old.TARGETS}
known={'1811.03761','1904.12017','2102.06704','2201.13320','2212.02387'}
ids=['1811.03761','1904.12017','2102.06704','2111.03820','2201.13320','2207.04555','2212.02387','2306.04961','2306.05100','2309.05204','2310.09804','2501.04443','2501.09516','2501.18312','2503.07594','2504.19004']
rows=[]
for pid in ids:
 for variant,condition in [('codex','Codex原生-完整复现-Goal'),('reasflow','ReasFlow实验Agent-完整复现-Goal')]:
  matches=list((ROOT/'reports/cpu30/analysis-2026-09-06/evidence').glob(f'*/agent_reproduction/runs/{pid}/{condition}/第003次运行/workspace'))
  assert len(matches)==1,(pid,variant,matches)
  workspace=matches[0]
  if pid in known:
   t=old_targets[(pid,variant)];source=t[4];adapter=source/'adapters'/t[5]
   contract=source/'papers'/pid/'contract.json'
   paper_review=ROOT/'reports/judge-hardening-cpu30-20260915/paper_reviews'/f'{pid}.json'
   adapter_review=ROOT/'reports/judge-hardening-cpu30-20260915/adapter_reviews'/f'{t[0]}.json'
   public=source/'public'/pid/'public_cases.json'
  else:
   adapter=REPORT/'adapters'/pid/variant;contract=REPORT/'papers'/pid/'contract.json'
   paper_review=REPORT/'paper_reviews'/f'{pid}.json';adapter_review=adapter/'review.json'
   public=REPORT/'public'/pid/'public_cases.json'
  rows.append(dict(target=f'{pid}-{variant}',paper_id=pid,variant=variant,workspace=str(workspace),
   workspace_digest=_snapshot_digest(_workspace_snapshot(workspace)),paper_path=str(ROOT/'datasets/benchmarks/cpu30_v1/input'/pid/'paper.pdf'),
   contract_path=str(contract),paper_review_path=str(paper_review),adapter_path=str(adapter/'adapter.py'),
   bindings_path=str(adapter/'bindings.json'),adapter_review_path=str(adapter_review),public_path=str(public),
   environment_actions_path=str(adapter/'environment_actions.json'),previously_tested=pid in known))
(REPORT/'TARGETS.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2))
(REPORT/'PUBLIC_TARGETS.json').write_text(json.dumps([{k:r[k] for k in ['target','paper_id','variant','workspace','workspace_digest','public_path','adapter_path','bindings_path','environment_actions_path','adapter_review_path']} for r in rows],ensure_ascii=False,indent=2))
print('Recorded',len(rows),'workspaces across',len(ids),'papers')
