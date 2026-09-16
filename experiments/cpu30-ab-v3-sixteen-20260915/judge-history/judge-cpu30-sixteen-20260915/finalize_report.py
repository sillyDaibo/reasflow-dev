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
 names={'1811.03761':'RSA','1904.12017':'ADMM stratified','2102.06704':'ProxRR / FedRR','2111.03820':'DPG-RR','2201.13320':'BEER','2207.04555':'APDG','2212.02387':'DREAM','2306.04961':'IRLS','2306.05100':'ProxSkip-VIP-FL','2309.05204':'PIRL1-AM（非加速）','2310.09804':'Byz-DASHA-PAGE','2501.04443':'LocalSGD / 简化 SCAFFOLD','2501.09516':'ManPQN','2501.18312':'PPS primal-dual','2503.07594':'SCAFFOLD','2504.19004':'SGS-CD'}
 def label(r):
  a=r['assessment'];n=a['numeric_mismatches'];got=sum(c['complete_observations'] for c in a['cases']);required=sum(c['required_observations'] for c in a['cases'])
  text='通过选定实验' if a['acceptance']=='eligible_on_tested_scope' else '数值差异' if r['status']=='INCONSISTENT' else '未完整判定'
  return f'{text}；观测 {got}/{required}；差异 {n}'
 lines=['# CPU30 16 篇算法 Judge 测试报告','',
 '**范围已扩大到全部 16 篇、32 个历史复现仓库。** 每个仓库最终保留两次评估，共 64 次；两次逐值比较及最终 assessment 完全一致。全部原 workspace 与初始内容摘要一致，论文标准、容差未根据实现结果调整。','',
 f'最终有 **{eligible} 个仓库通过选定实验、{counts["INCONSISTENT"]} 个完整观测后存在数值差异、{counts["INCONCLUSIVE"]} 个未能完成完整判定**。后者中 {partial_diffs} 个仍有真实可比较状态的数值差异。评估全部32个，不等于32个都已经得到完整的算法正确性结论。','',
 '“通过”只表示这些有限小实验通过；“差异”仍需区分算法、归一化、精度和允许变体，不能将差异位置数当作缺陷数。','',
 '## 全部 16 篇结果','',
 '| 论文 ID / 本轮算法 | Codex 原生 | ReasFlow |','|---|---|---|']
 for pid,title in names.items():lines.append(f'| {pid} / {title} | {label(representatives[pid+"-codex"])} | {label(representatives[pid+"-reasflow"])} |')
 lines+=['',
 '## 如何准备和独立复核','',
 '原5篇沿用已经冻结并独立复核的实验；新增11篇由三名论文agent分组只读原PDF，各准备2个小实验，共22个实验、568组待观测状态。随后交叉复核其他agent的论文，独立编写算术程序重算全部预期，均在既定容差内。出题者与复核者都没有读取被测workspace、调用脚本或实际结果。','',
 '另外三名新的agent只读公开输入与原源码，编写22套调用脚本；每套由另一名agent或root独立审查公开输入、原源码与脚本。root仅审查2111.03820两套，并在读取该目标私有数值比较之前完成记录。审核记录绑定具体标准、脚本、函数列表和workspace版本。信息边界与分工见 PREPARATION_PROVENANCE.json。','',
 '调用脚本保留原算法和原有可用的目标函数、近端映射、压缩器及聚合函数。必要的合成目标输入、随机实现与观测包装逐项登记；原算法更新不被改写。脚本缺少的状态不能从论文公式补造。','',
 '## 本轮实际发现的限制','',
 '- APDG / ReasFlow：内部强制选择谱参数，不能接受公开实验参数。其运行轨迹保存在 diagnostics，标准 observations 为空，不能用不同参数下的数值差异判算法错误。',
 '- PPS 两套：原仓库提供的是 graph barycenter Algorithm 3，缺少公开实验要求的 generic Algorithm 2 接口。本轮仅观察原 signed PPS 的真实入参、返回、质量分解与抽样索引；其余递推没有伪造。',
 '- PIRL1-AM / Codex：独立 z0 无法表达，后续不同初值语义的轨迹移入 diagnostics，只保留可比较初始梯度。ReasFlow 在公开 (1,3) 输入上出现原始维度赋值错误，不能完成实验。',
 '- ManPQN 两套：无法同时表达声明的初始拟牛顿矩阵、相关参数及精确内解条件。仅保留匹配的初始点及梯度，其余原运行日志作诊断。论文允许的某些非精确内解不应被精确轨迹要求误判为算法错误。',
 '- SGS-CD / ReasFlow：源码使用 grad/L[e]，提供的 stepsizes 属性未进入更新；无法接受本实验的固定 eta。保留首事件可比较状态，之后明确缺失。',
 '- IRLS 两套：能执行原始迭代，但部分论文谱权/完整权重算子不能作为真实源状态取得。已有可比较状态存在差异，缺项与差异分别记录。',
 '- RSA、DREAM 的既有覆盖问题仍保留；BEER / ReasFlow 的4个细小差异仍提示精度与数学含义复查，没有事后放宽容差或强行判通过。','',
 '这些限制既可能来自实现缺项，也可能来自合法变体、固定参数、求解精度或观测方式。当前结果必须分开看“实验能否表达”“真实观测是否匹配”，不能把所有未通过都算成复现算法错误。','',
 '## 审查推动的修正','',
 'APDG / ReasFlow、PIRL1-AM / Codex、ManPQN 两套原适配草稿包含不满足公开设置的后续轨迹。独立审查要求将这些数据移入 diagnostics，仅保留真正可比较的 observations，并重新核验脚本哈希。本轮未读取实际数值比较来调整答案或容差。','',
 f'共进行了 {len(all_attempts)} 次评估尝试。2503.07594 / Codex 的最初两次因新环境缺 sklearn 失败：原包 __init__ 会导入 datasets.py。补齐源码要求的 scikit-learn 后，在新目录重新评估两次；最终统计采用修复环境后的两次结果。初始失败保留，见 ENVIRONMENT_FIXES.md。','',
 '## 对 Judge 的结论','',
 '扩大到16篇后，可以稳定运行固定的论文实验并区分一部分实现差异；独立审查也实际阻止了不同参数/初始状态导致的错误比较。当前最大限制已很清楚：不少仓库不能忠实表达统一实验，或无法提供要求的观测，所以仍有较多“未完整判定”。','',
 '因此，现在可以把它作为有证据的算法检查工具，但不能作为1万篇语料库的唯一正确性证明。后续需要提高对合法算法变体、求解精度和不同接口的支持，并设计较少依赖内部变量表示的论文实验；同时保留固定标准、独立复核和不可判定结果。','',
 '本轮未改算法Judge生产代码，沿用上一轮已通过105项程序测试并做过独立代码审查的版本。新增的是11篇标准/复算、22套调用/审核，以及16篇全量运行证据。此前6种故意错误的对照结果不重新计入本轮16篇准确率。','',
 '**本轮没有调用独立模型API或使用API key。** 论文与调用脚本由Codex子agent准备、复核，数值回放由程序执行。两次结果一致只验证固定标准与脚本下的执行稳定性，没有验证自动出题/AI复核跨次一致性、外部API全链路或大规模运行成本。','',
 '## 证据入口与复跑','',
 f'- [完整机器结果]({REPORT}/FINAL_SUMMARY.json)：最终64次及所有早期尝试，每条链接到原始result.json。',
 f'- [原仓库与输入清单]({REPORT}/TARGETS.json)：32个原workspace路径、标准与脚本路径。',
 f'- [版本绑定]({REPORT}/FINAL_ARTIFACT_VERSIONS.json)：原workspace、标准、脚本、审核与环境动作摘要。',
 f'- [准备和审核分工]({REPORT}/PREPARATION_PROVENANCE.json)。',
 f'- 论文依据与首次推演：{REPORT}/papers/<id>/；独立复算：{REPORT}/paper_reviews/。',
 f'- 调用和独立审核：{REPORT}/adapters/<id>/<codex|reasflow>/。','',
 '```bash',
 '/tmp/optirepro-paper-judge-20260915/bin/python reports/judge-cpu30-sixteen-20260915/run_validation.py --repeats 2 --workers 4',
 '```','']
 (REPORT/'REPORT.md').write_text('\n'.join(lines))
 (REPORT/'WORKLOG.md').write_text('# CPU30 16篇算法 Judge 工作记录\n\n已完成16篇、32个workspace的两次评估，最终64次结果已核验；原workspace未变。详见 REPORT.md 与 FINAL_SUMMARY.json。\n')
 print(json.dumps({k:v for k,v in summary.items() if k not in {'rows','all_attempts','batches'}},ensure_ascii=False,indent=2))
if __name__=='__main__':main()
