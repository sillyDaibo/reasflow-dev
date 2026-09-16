"""Public-input-only smoke; never read contracts or Judge comparisons."""
import json,os,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];OUT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'repo_judge'))
from src.judge.execution import _readonly_tree,_workspace_snapshot,_snapshot_digest
for t in json.loads((OUT/'PPS_PUBLIC_TARGETS.json').read_text()):
 w=Path(t['workspace']);d=Path(t['adapter_dir'])
 before=_snapshot_digest(_workspace_snapshot(w));assert before==t['workspace_digest']
 env=dict(os.environ,OPTIREPRO_WORKSPACE=str(w),OPTIREPRO_CASES=t['public_path'],PYTHONDONTWRITEBYTECODE='1')
 with _readonly_tree(w):
  result=subprocess.run([sys.executable,str(d/'adapter.py')],env=env,capture_output=True,text=True,timeout=60)
 (d/'public_smoke.stdout').write_text(result.stdout);(d/'public_smoke.stderr').write_text(result.stderr)
 assert before==_snapshot_digest(_workspace_snapshot(w))
 print(t['target'],result.returncode,flush=True)
 if result.returncode:print(result.stderr);raise SystemExit(result.returncode)
 cases=json.loads(result.stdout.split('OPTIREPRO_OBSERVATIONS=')[-1])['cases']
 print([(c['id'],len(c['observations']),len(c.get('missing_observations',[]))) for c in cases],flush=True)
