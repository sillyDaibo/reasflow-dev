"""Synthetic canaries only; never loads benchmark contracts or answers."""
import asyncio,hashlib,json,sys,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'repo_judge'))
from src.judge import execution as runtime
from src.judge.algorithm_pipeline import execute
from src.judge.paper_contract import contract_digest,public_contract
from src.judge.review_records import json_digest

def write(p,x):p.write_text(json.dumps(x))
async def main():
 with tempfile.TemporaryDirectory(prefix='optirepro-implementation-review-') as d:
  root=Path(d).resolve();repo=root/'workspace';repo.mkdir()
  (repo/'core.py').write_text('def step(x):\n    return x + 1\n')
  paper=root/'paper.txt';paper.write_text('Synthetic audit canary: initialize x to zero and add one. Observe both zero and one. This is not a research benchmark or a hidden answer. '*2)
  sha=hashlib.sha256(paper.read_bytes()).hexdigest()
  contract={'schema_version':'optirepro.paper_algorithm_contract.v1','paper':{'paper_id':'synthetic','title':'Audit canary','sha256':sha},'algorithm':{'name':'addition','citations':['Synthetic text'],'core_mechanisms':['addition'],'assumptions':[]},'cases':[{'id':'toy','purpose':'Version binding canary','derivation':'Synthetic 0 + 1 = 1. No benchmark data.','covers':['addition'],'inputs':{'x0':0},'parameters':{},'atol':0,'rtol':0,'expected':[{'step':0,'name':'x','value':0},{'step':1,'name':'x','value':1}]}]}
  cp=root/'toy_contract.json';write(cp,contract)
  paper_review={'schema_version':'optirepro.paper_review.v1','basis':'original_paper_only','reviewer_id':'synthetic-test-only','decision':'approved','summary':'Synthetic canary only','scope_notes':['Not a real paper review.'],'contract_digest':contract_digest(contract),'cases':[{'case_id':'toy','decision':'approved','reason':'Synthetic addition','citations':['Synthetic text']} ]}
  pr=root/'paper_review.json';write(pr,paper_review)
  adapter=root/'adapter.py';adapter.write_text('import json, os, sys\nsys.path.insert(0, os.environ["OPTIREPRO_WORKSPACE"])\nfrom core import step\nx = json.load(open(os.environ["OPTIREPRO_CASES"]))["cases"][0]["inputs"]["x0"]\nprint("OPTIREPRO_OBSERVATIONS=" + json.dumps({"cases":[{"id":"toy","observations":[{"step":0,"name":"x","value":x},{"step":1,"name":"x","value":step(x)}]}]}))\n')
  if "--unknown-status" in sys.argv:
   adapter.write_text(adapter.read_text().replace('"id":"toy","observations"', '"id":"toy","status":"unsupported","observations"'))
  bindings=[{'path':'core.py','symbol':'step'}]
  ar={'schema_version':'optirepro.adapter_review.v1','basis':'public_inputs_and_source_only','reviewer_id':'synthetic-test-only','decision':'approved','summary':'Synthetic adapter canary','scope_notes':['No algorithm replacement.'],'substitutions':[],'public_digest':json_digest(public_contract(contract)),'adapter_sha256':hashlib.sha256(adapter.read_bytes()).hexdigest(),'workspace_digest':runtime._snapshot_digest(runtime._workspace_snapshot(repo)),'bindings_digest':json_digest(bindings)}
  arp=root/'adapter_review.json';write(arp,ar)
  spec={'evaluation_id':'adapter-toctou','paper_path':str(paper),'contract_path':str(cp),'paper_review_path':str(pr),'adapter_review_path':str(arp),'adapter':{'path':str(adapter),'bindings':bindings},'environment_actions':[]}
  sp=root/'spec.json';write(sp,spec)
  old=runtime._apply_action
  old_sha=runtime._sha256_file
  def mutate_during_setup(repo,work,action,env):
   result=old(repo,work,action,env)
   if "--unreadable-artifact" in sys.argv:
    def unreadable(path):
     if path == work/"probes/adapter.py": raise OSError("synthetic unreadable artifact")
     return old_sha(path)
    runtime._sha256_file=unreadable
    return result
   path=work/'probes/adapter.py';path.write_text(path.read_text()+'\n# changed after independent review\n')
   frozen=root/'judge/evaluations/adapter-toctou/algorithm/frozen/adapter.py';frozen.write_text(frozen.read_text()+'\n# frozen changed after independent review\n')
   return result
  runtime._apply_action=mutate_during_setup if "--unknown-status" not in sys.argv else old
  try: result=await execute(str(repo),str(sp),run_root=str(root))
  finally:
   runtime._apply_action=old
   runtime._sha256_file=old_sha
  executed=root/'runtime/adapter-toctou/probes/adapter.py'
  print(json.dumps({'status':result['status'],'reason_code':result['reason_code'],'acceptance':result['assessment']['acceptance'],'executed_adapter_matches_review':hashlib.sha256(executed.read_bytes()).hexdigest()==ar['adapter_sha256'],'source_integrity':result['source_integrity']},indent=2))
asyncio.run(main())
