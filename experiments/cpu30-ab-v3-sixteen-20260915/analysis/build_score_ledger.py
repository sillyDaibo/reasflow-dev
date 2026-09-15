"""Read-only analysis of frozen CPU30 evidence; rebuild every rubric's score ledger."""
import json,hashlib,re,statistics,collections
from pathlib import Path
from markdown_format import literal_prose, quote_evidence, code_block
ROOT=Path('/Users/zanehuang/work/OptiRepro'); OUT=Path(__file__).resolve().parent
E=OUT/'evidence'; LEDGER=OUT/'ledgers'; LEDGER.mkdir(exist_ok=True)
def j(p):return json.loads(p.read_text())
def link(p,label,line=None):return f'[{label}]({p.resolve()}{":"+str(line) if line else ""})'
def clean(t):return str(t).replace('|','\\|').replace('\n','<br>')
def lines(p):
 text=p.read_text().splitlines();return {m.group(1):i for i,s in enumerate(text,1) if (m:=re.search(r'"id": "([^"]+)"',s))}
weights={}; inventory=[]; runs={}; checks=[]
for host in sorted(E.iterdir()):
 if not (host/'inventory.json').exists():continue
 inv=j(host/'inventory.json'); inventory.append({'host':host.name,'captured_at_utc':inv['captured_at_utc']})
 for item in inv['inventory']:
  if item['queue']!='cpu30-ab-v3' or not item['evaluations'] or item['state']!='terminal':continue
  p=host/Path(item['evaluations'][0]).relative_to('/home/hzy/optirepro')
  manifest=j(p/'EVALUATION_MANIFEST.json')
  assert manifest['status']=='completed'
  runs.setdefault(item['paper_id'],{})[item['condition']]={'path':p,'manifest':manifest,'item':item,'loops':{l:j(p/f'results/evaluation_{l}.json') for l in ['midloop','bigloop']}}
pairs={p:d for p,d in sorted(runs.items()) if set(d)=={'A','B'}}
allrows=[]; summaries=[]; group_rows=[]; audit_flags=[]
for pid,d in pairs.items():
 parts=[f'# {pid}：逐项评分原账', '', '以下逐项保留量规描述、验证规则、权重和 Judge 原始证据/说明。判定 1 得到该项全部权重，判定 0 得 0 分；这些说明是原 Judge 判词，不代表本报告已经逐条重新裁决。主报告另列人工复核发现。','']
 summary={'paper_id':pid}
 for loop in ['midloop','bigloop']:
  rp=ROOT/f'judge/rubrics/CPU30_{pid.replace(".","_")}/CPU30_llm_generated_v2/files/rubrics_llm_{loop}.json'; rub=j(rp); ri={r['id']:r for r in rub['rubrics']}; rlines=lines(rp)
  result={c:{r['id']:r for r in d[c]['loops'][loop]['results']} for c in ['A','B']}; total=sum(r['weight'] for r in ri.values())
  parts += [f'## {loop}：{len(ri)} 项，总权重 {total}', '',link(rp,'量规原文')+'；'+'；'.join(link(d[c]['path']/f'results/evaluation_{loop}.json',f'{c} 原始判定') for c in ['A','B']), '']
  summary[loop]={}
  for c in ['A','B']:
   assert set(ri)==set(result[c]),(pid,loop,c,'IDs mismatch')
   data=d[c]['loops'][loop]; earned=sum(ri[i]['weight'] for i,r in result[c].items() if r['verdict']==1); score=round(earned/total,4)
   assert score==data['summary']['total_score'],(pid,loop,c,score,data['summary'])
   assert len(result[c])==data['summary']['total_rubrics']
   assert sum(r['error'] for r in result[c].values())==0
   assert hashlib.sha256(rp.read_bytes()).hexdigest()==d[c]['manifest']['rubrics']['files'][loop]['sha256']
   raw=d[c]['path']/f'results/evaluation_{loop}.json'
   expected=d[c]['manifest']['finalized_artifacts']['files'].get(f'results/evaluation_{loop}.json')
   assert expected and hashlib.sha256(raw.read_bytes()).hexdigest()==expected['sha256']
   summary[loop][c]={'earned':earned,'weight':total,**data['summary']}
   checks.append({'paper_id':pid,'condition':c,'loop':loop,'rubrics_hash_match':True,'result_hash_match':True,'recomputed_score_match':True,'item_count':len(ri)})
   parts += [f'**{c}：{earned}/{total} = {score*100:.2f}%；条目通过 {data["summary"]["passed"]}/{len(ri)}；门槛 {data["summary"]["pass_threshold"]*100:.0f}%，{"通过" if data["summary"]["gate_passed"] else "未通过"}。**','']
  # Summaries grouped by algorithm or experiment, equal weighting still original within groups.
  groups=collections.defaultdict(list)
  for i,r in ri.items(): groups[(r['dimension'],(r.get('verification') or {}).get('spec',{}).get('experiment_id','算法实现'))].append(i)
  parts+=['| 维度 / 实验组 | 项数 | A 加权得分 | B 加权得分 |','|---|---:|---:|---:|']
  for (dim,ex),ids in groups.items():
   den=sum(ri[i]['weight'] for i in ids); earned={c:sum(ri[i]['weight'] for i in ids if result[c][i]['verdict']==1) for c in ['A','B']}
   parts.append(f'| {dim} / {clean(ex)} | {len(ids)} | {earned["A"]}/{den} | {earned["B"]}/{den} |')
   group_rows.append({'paper_id':pid,'loop':loop,'dimension':dim,'experiment':ex,'n':len(ids),'denominator':den,**earned})
  parts+=['']
  for i,r in ri.items():
   parts += [f'### {pid} / {loop} / {i}', '',
    '**检查内容：** '+literal_prose(r['description']), '',
    f'**类别与权重：** `{r["dimension"]}`；`{r["priority"]}`；权重 {r["weight"]}（本层占比 {100*r["weight"]/total:.3f}%）。', '',
    '**论文定位：** '+literal_prose(r.get('context') or '量规未提供')+'。'+link(rp,'原始量规',rlines.get(i)), '']
   v=r.get('verification')
   if v:
    spec=v.get('spec',{}); typ=v.get('type'); why=[]
    for field,label in [('experiment_id','目标实验'),('dataset','数据集'),('method','方法'),('metric','指标')]:
     if field in spec: why.append(f'{label}={spec[field]}')
    if typ=='numerical':
     for field,label in [('expected_value','论文参考值'),('tolerance_abs','绝对容差'),('tolerance_rel','相对容差')]:
      if field in spec:why.append(f'{label}={spec[field]}')
     why.append('按指定容差核对当前运行测量值；超过容差得0')
    elif typ=='ranking':
     why.append('比较关系='+str(spec.get('order',spec.get('constraints','见完整spec'))))
     why.append('指标方向='+{'lower_is_better':'越低越好','higher_is_better':'越高越好'}.get(spec.get('direction'),str(spec.get('direction','见原规则'))))
    elif typ=='boolean':why.append('按scope/描述检查是否满足；满足得全部权重，否则得0')
    elif typ=='extensible':why.append('按开放文字任务检查scope；具体判断见两侧证据与理由')
    parts += ['**如何检查：** '+literal_prose('；'.join(why)+'。'), '',
     '**完整验证规则：**', '',code_block(json.dumps(v,ensure_ascii=False,indent=2),'json'),'']
   else:parts += ['**如何检查：** algorithm_impl 无单独 verification spec，Judge 对照描述、论文上下文及仓库代码作二元判断。','']
   for c in ['A','B']:
    row=result[c][i]; jp=d[c]['path']/f'results/evaluation_{loop}.json'; jl=lines(jp)
    parts += [f'**{c}：{"通过" if row["verdict"]==1 else "未通过"}，{r["weight"] if row["verdict"]==1 else 0}/{r["weight"]} 分。**', '',
     f'Judge confidence=`{row.get("confidence")}`；error=`{str(row.get("error")).lower()}`。'+link(jp,'该项判词',jl.get(i)), '',
     '**证据（Judge 原文）：**', '',quote_evidence(row.get('evidence','')), '',
     '**理由（Judge 原文）：**', '',quote_evidence(row.get('note','')), '']
    allrows.append({'paper_id':pid,'loop':loop,'condition':c,'id':i,'weight':r['weight'],'criterion':r,**row})
    txt=row.get('evidence','')+' '+row.get('note','')
    other_runs=sorted(set(re.findall(r'第\d{3}次运行',txt)) - {'第003次运行'})
    if other_runs:audit_flags.append({'paper_id':pid,'loop':loop,'condition':c,'id':i,'verdict':row['verdict'],'flag':'other_run_reference','runs':other_runs,'evidence':txt})
    other_condition='Codex原生-完整复现-Goal' if c=='B' else 'ReasFlow实验Agent-完整复现-Goal'
    if '/'+other_condition+'/' in txt:audit_flags.append({'paper_id':pid,'loop':loop,'condition':c,'id':i,'verdict':row['verdict'],'flag':'other_condition_path_reference','evidence':txt})
  parts+=['']
 (LEDGER/f'{pid}.md').write_text('\n'.join(parts))
 summaries.append(summary)
agg={}
for l in ['midloop','bigloop']:
 a=[s[l]['A']['total_score'] for s in summaries]; b=[s[l]['B']['total_score'] for s in summaries]
 agg[l]={'A_mean':statistics.mean(a),'B_mean':statistics.mean(b),'B_minus_A_mean':statistics.mean(y-x for x,y in zip(a,b)),'A_median':statistics.median(a),'B_median':statistics.median(b),'B_wins':sum(y>x for x,y in zip(a,b)),'B_losses':sum(y<x for x,y in zip(a,b)),'ties':sum(y==x for x,y in zip(a,b)),'A_gate_passed':sum(s[l]['A']['gate_passed'] for s in summaries),'B_gate_passed':sum(s[l]['B']['gate_passed'] for s in summaries)}
 for c in ['A','B']:
  agg[l][c+'_micro_score']=sum(s[l][c]['earned'] for s in summaries)/sum(s[l][c]['weight'] for s in summaries)
  agg[l][c+'_item_count']=sum(s[l][c]['total_rubrics'] for s in summaries)
# Leave-one-paper-out descriptive robustness only.
agg['leave_one_paper_out_bigloop_delta_range']=[min(statistics.mean(s['bigloop']['B']['total_score']-s['bigloop']['A']['total_score'] for s in summaries if s['paper_id']!=omit['paper_id']) for omit in summaries),max(statistics.mean(s['bigloop']['B']['total_score']-s['bigloop']['A']['total_score'] for s in summaries if s['paper_id']!=omit['paper_id']) for omit in summaries)]
# Mechanical sensitivity by verification TYPE (not posthoc pass/fail labels).
sensitivity={}
for typ in sorted(set((r['criterion'].get('verification') or {}).get('type','algorithm_impl') for r in allrows if r['loop']=='bigloop')):
 vals={}
 for c in ['A','B']:
  selected=[r for r in allrows if r['loop']=='bigloop' and r['condition']==c and (r['criterion'].get('verification') or {}).get('type','algorithm_impl')==typ]
  vals[c]={'n':len(selected),'weight':sum(r['weight'] for r in selected),'earned':sum(r['weight'] for r in selected if r['verdict']==1)}
 sensitivity[typ]=vals
result={'snapshot':inventory,'paper_count':len(pairs),'summaries':summaries,'aggregate':agg,'bigloop_verification_type_sensitivity':sensitivity,'groups':group_rows,'cross_run_reference_flags':audit_flags,'verification':checks}
(OUT/'score_analysis.json').write_text(json.dumps(result,ensure_ascii=False,indent=2))
(OUT/'rubric_ledger.json').write_text(json.dumps(allrows,ensure_ascii=False,indent=2))
print(json.dumps({'paper_count':len(pairs),'rubric_judgments':len(allrows),'aggregate':agg,'sensitivity':sensitivity,'cross_run_flags':audit_flags},ensure_ascii=False,indent=2))
