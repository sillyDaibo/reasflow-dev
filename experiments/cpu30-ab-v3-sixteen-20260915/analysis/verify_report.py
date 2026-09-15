"""Validate the assembled report's completeness, evidence links and snapshot bytes."""
from pathlib import Path
import json,re,hashlib
O=Path(__file__).resolve().parent
p=O.parent/'CPU30_COMPLETED_AB_DEEP_ANALYSIS_2026-09-06.md';text=p.read_text()
d=json.loads((O/'score_analysis.json').read_text()); expected={s['paper_id'] for s in d['summaries']}
assert len(expected)==16
assert len(list((O/'papers').glob('*.md')))==16
assert len(d['verification'])==64
assert len(json.loads((O/'rubric_ledger.json').read_text()))==3262
assert len(re.findall(r'^# ',text,re.M))==1
assert len(re.findall(r'^##### \d{4}\.\d{5} / (?:midloop|bigloop) / (?:alg|setup|res)-\d+',text,re.M))==1631
assert text.count('<details>')==16 and text.count('</details>')==16
missing=[];oor=[];links=0
cache={}
for m in re.finditer(r'\]\((/[^\n)]+)\)',text):
 target=m.group(1);match=re.match(r'^(.*?)(?::(\d+))?$',target);path=Path(match[1]);links+=1
 if not path.exists():missing.append(target)
 elif match[2]:
  if path not in cache:cache[path]=len(path.read_text(errors='replace').splitlines())
  if int(match[2])>cache[path]:oor.append(target)
assert not missing,missing
assert not oor,oor
hashed=0
for file in (O/'evidence').glob('*/SHA256.json'):
 for rel,sha in json.loads(file.read_text()).items():
  target=file.parent/rel
  assert hashlib.sha256(target.read_bytes()).hexdigest()==sha,str(target)
  hashed+=1
r={'report':str(p),'report_sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'report_bytes':p.stat().st_size,'report_lines':len(text.splitlines()),'papers':16,'evaluations':32,'loop_result_files':64,'unique_rubrics':1631,'AB_rubric_judgments':3262,'local_links_checked':links,'missing_links':missing,'out_of_range_line_links':oor,'snapshot_files_hash_verified':hashed,'status':'passed'}
(O/'DOCUMENT_VERIFICATION.json').write_text(json.dumps(r,ensure_ascii=False,indent=2));print(json.dumps(r,ensure_ascii=False,indent=2))
