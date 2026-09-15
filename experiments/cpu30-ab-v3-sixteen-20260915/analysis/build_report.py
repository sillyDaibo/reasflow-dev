"""Assemble the Chinese report and its unabridged per-rubric appendix."""
from pathlib import Path
import json,re
from markdown_format import normalize_bold, shift_headings
O=Path(__file__).resolve().parent; ROOT=O.parents[2]; D=json.loads((O/'score_analysis.json').read_text())
MAIN=O.parent/'CPU30_COMPLETED_AB_DEEP_ANALYSIS_2026-09-06.md'
def link(p,label):return f'[{label}]({p.resolve()})'
parts=[(O/'report_overview.md').read_text()]
parts += ['## 评分总表：原始 Judge 分，按论文配对',
 '',
 '| 论文 | A Mid：得分权重/总权重 | B Mid | A Big | B Big | Big B−A（百分点） |',
 '|---|---:|---:|---:|---:|---:|']
for s in D['summaries']:
 cells=[link(O/'papers'/f'{s["paper_id"]}.md',s['paper_id'])]
 for l,c in [('midloop',
 'A'),('midloop',
 'B'),('bigloop',
 'A'),('bigloop',
 'B')]:
  a=s[l][c];cells.append(f'{a["earned"]}/{a["weight"]} = {100*a["total_score"]:.2f}%')
 cells.append(f'{100*(s["bigloop"]["B"]["total_score"]-s["bigloop"]["A"]["total_score"]):+.2f}')
 parts.append('| '+' | '.join(cells)+' |')
parts += ['',
 '表中的分子是通过项的权重之和，不能当成通过条目数。数据由'+link(O/'build_score_ledger.py',
 '核账脚本')+'从原始结果与相同哈希的量规重算；机器可读汇总见'+link(O/'score_analysis.json',
 'score_analysis.json')+'。',
 '',
 '| 配对统计 | A | B | 说明 |',
 '|---|---:|---:|---|']
for l in ['midloop',
 'bigloop']:
 a=D['aggregate'][l]
 parts += [f'| {l} 每篇等权均值 | {a["A_mean"]*100:.2f}% | {a["B_mean"]*100:.2f}% | B−A {a["B_minus_A_mean"]*100:+.2f} pp |',f'| {l} 中位数 | {a["A_median"]*100:.2f}% | {a["B_median"]*100:.2f}% | 16篇 |', f'| {l} 通过门槛 | {a["A_gate_passed"]}/16 | {a["B_gate_passed"]}/16 | B胜/负/平 {a["B_wins"]}/{a["B_losses"]}/{a["ties"]} |',f'| {l} 全部条目直接加权 | {a["A_micro_score"]*100:.2f}% | {a["B_micro_score"]*100:.2f}% | 每篇条目数不等，勿替代论文等权指标 |']
parts += ['',
 'Midloop 内再分开：algorithm_impl 的每篇等权平均为 A **75.30%**、B **79.05%**；exp_setup 为 A **74.66%**、B **75.04%**。这支持“B 的部分实现检查表现较好”的有限描述，不能推导出“B 的算法都正确”或“B 实验更完整”。Midloop 总分不是这两列均值的简单平均，它按本层每项权重聚合。',
 '',
 'Bigloop 的 B−A 均值在逐一去掉任意一篇后仍落在 **−7.13 至 −3.58 pp**。因此本批的负差不是单篇极端样本独自造成的；但这也不是统计显著性检验，更不能排除量规共同错误、配置差异和未完成样本造成的偏差。没有多次独立随机运行，本报告不报告因果效应或统计显著性。',
 '',
 '旧阶段报告中配对 Midloop 的通过数和胜负表述需要纠正：本次重新按结果字段核对为 **A 7、B 8；B胜7、负6、平3**。历史报告保留不覆盖。',
 '']
parts += ['## 评分究竟怎样计算',
 '',
 '本批使用 `RepoJudge-llmmelon-ClaudeSonnet4.6适配-v2` 与每篇的 `CPU30_llm_generated_v2` 量规。请求模型是 `claude-sonnet-4-6`，manifest 中 provider 在 adapter validation 阶段回报 `mcs-5`；这两项如实区分，不能仅凭请求名确认实际服务端模型身份。',
 '',
 '### 两层检查范围',
 '',
 '| 层级 / 维度 | 回答的问题 | 典型证据 | 不能据此断言 |',
 '|---|---|---|---|',
 '| Midloop / algorithm_impl | 更新式、算子、压缩器、控制变量、数据流是否匹配量规 | 源码、公式对应关系 | 所有实验有效、理论证明已重证 |',
 '| Midloop / exp_setup | 数据、拆分、超参数、网络、种子、预算、基线是否匹配要求 | 配置、实验入口、运行记录 | 只要有配置就真的跑完了 |',
 '| Bigloop / exp_results | 表值、方法排序、趋势、图或其他输出是否支持目标 | 当前运行的测量、曲线和结果文件 | 通过门槛就是全文所有claim成立 |',
 '',
 '每一条量规有 ID（`alg-*` / `setup-*` / `res-*`）、description、context、priority、weight；实验相关条目另有 verification.type/spec。该 spec 规定目标实验、数据集、方法、指标、参考值、容差或排序。Judge 输出 verdict=1 或0、confidence、evidence、note、error。**它是工具辅助的模型裁决，不能把 verdict 误称为完全确定的数学判定。**',
 '',
 '### 二元判定、权重和门槛',
 '',
 '```text\n条目得分_i = weight_i × 1(verdict_i = 1)\n该层总分 = round(Σ条目得分_i / Σweight_i, 4)\nMidloop gate：该层总分 >= 0.80\nBigloop gate：该层总分 >= 0.85\n```',
 '',
 '本批量规通常 primary 权重2，secondary/tertiary 权重1；核账实际读取每条 `weight`，不会凭 priority 自行猜权重。confidence 不乘进分数，没有0.5分的部分通过；一项只有部分约束满足仍可能全项得0。`by_priority.score` 是该优先级通过条目数/条目总数，与整层按 weight 的汇总不是同一个计算口径。',
 '',
 '实现依据：'+link(ROOT/'judge/versions/RepoJudge/llmmelon-ClaudeSonnet4.6适配_v2/source/repo_judge/src/judge/runner.py',
 'runner.py 中 _aggregate')+'、'+link(ROOT/'judge/versions/RepoJudge/llmmelon-ClaudeSonnet4.6适配_v2/source/repo_judge/src/schemas/models.py',
 '量规/结果 schema')+'。本报告核对64份评分的全部 ID 集合、分子分母、量规哈希、manifest登记的结果哈希；全部一致。**哈希和算术一致只能保证所分析的是这些原账，不能保证原账的科学判断正确。**3,262次判定的 error 均为 false，也仅表示没有被记录为技术错误。',
 '',
 '### 每种检查如何造成得分差',
 '',
 '| verification.type | 判断方式 | 本批主要风险 |',
 '|---|---|---|',
 '| numerical | 当前结果与expected_value比较，按spec中的绝对/其他容差判断 | 比论文更好但超出双向容差也可失败；跨硬件时间不可直接等同 |',
 '| ranking | 按direction解释方法优劣并检查order，通常要求指定比较全部满足 | 平局、曲线交叉、终点和全过程口径不同 |',
 '| boolean | 特定设置/输出/现象是否存在且满足scope | 文件存在与内容正确、配置存在与完成运行可能混淆 |',
 '| extensible | 依据scope/task_check或文字描述检查较开放的主张 | 近似程度和趋势解释可能不一致 |',
 '',
 '例如 `1904.12017 / res-004` 检查 stratified test error=0.27±0.01。A 当前值约0.30303，差值为0.30303−0.27=0.03303，超出容差，原账判0；需注意原Judge文字曾写成0.0303，这是判词算术笔误，但不改变该项超容差结论。B 的约0.262626距0.27约0.007374，落在容差内，判1。`res-007` 的方法排序又是单独的2分检查：即使某个模型数值接近论文，也不能自动推出它严格优于所有基线。',
 '',
 '另一个聚合例子是 RSA：A Bigloop 的22项合计总权重36，通过权重35，所以为35/36=97.22%；这不是“论文复现程度恰好97.22%”的自然物理量，而是所选量规和权重下的得分。',
 '',
 '### 按验证类型拆看 Bigloop',
 '',
 '下表合并条目并按原始weight计算，专门说明哪些检查容易失败；它仍受到 ManPQN 大量 numerical 条目的影响，不是另一份公平的跨论文排名。',
 '',
 '| 检查类型 | 每侧项数 | 总权重 | A 得分 | B 得分 |',
 '|---|---:|---:|---:|---:|']
for typ,x in D['bigloop_verification_type_sensitivity'].items():
 a,b=x['A'],x['B'];parts.append(f'| {typ} | {a["n"]} | {a["weight"]} | {a["earned"]}/{a["weight"]} = {a["earned"]/a["weight"]*100:.2f}% | {b["earned"]}/{b["weight"]} = {b["earned"]/b["weight"]*100:.2f}% |')
parts += ['',
 'numerical 失败多说明精确表值与完整表格覆盖是明显短板，不能证明所有算法机制都错。另一方面，ranking 的 A/B 得分也只有43.68%/38.70%，说明低分并非仅由绝对数值容差或硬件时间造成。',
 '']
# Chapters are required, not silently omitted.
traj=O/'trajectory/trajectory_analysis.md'
assert traj.exists(),str(traj)
parts += ['## 实际 A/B 配置、交互和复现流程',
 '',
 '''下面概括保存轨迹中的共同流程。中性维护消息属于外部交互；两侧的算法诊断来自各自运行。是否发生具体动作，以后面的逐篇事件为准。

```mermaid
flowchart TD
    C[控制器注入论文任务 / Goal] --> A[A: Codex native]
    C --> B[B: Codex experiment角色 + ReasFlow技能]
    A --> P[读取论文、输入与官方快照]
    B --> P
    P --> I[实现 / 迁移算法与实验配置]
    I --> R[小型检查与正式实验]
    R --> D[检查数值、协议和输出]
    D -->|发现偏差，部分案例发生| I
    D --> V[声明、证据映射、文档、Validator与Git收口]
    V --> J[独立Judge读取交付工作区]
    J --> E[Midloop / Bigloop逐项原账]
    M[Monitor / 中性继续与恢复消息] -.-> A
    M -.-> B
```
''',re.sub(r'^(#{2,}) ', r'#\1 ', traj.read_text().split('\n',1)[1], flags=re.M),'',
 '## 逐篇论文：主张、结果与差距',
 '']
for s in D['summaries']:
 pid=s['paper_id']; paper=O/'papers'/f'{pid}.md';assert paper.exists(),str(paper)
 parts += [shift_headings(paper.read_text(),2),'',
 '**该篇完整评分明细：** '+link(O/'ledgers'/f'{pid}.md',f'{pid} 全部Midloop/Bigloop条目')+'。本文末尾亦完整嵌入同一明细。',
 '']
parts += [(O/'report_synthesis.md').read_text()]
parts += ['## 附录：全部逐项评分，保留原始判词',
 '',
 '共1,631个不同检查项、3,262次A/B判定。下方按论文折叠；展开即可看到每项检查内容、论文定位、验证spec、权重、A/B是否得分、原Judge证据与理由。判词保留原始语言以便逐字核对；其中不一致和已识别问题以正文审计为准。',
 '']
for s in D['summaries']:
 pid=s['paper_id'];parts += ['<details>',f'<summary>{pid}：展开全部逐项评分</summary>',
 '',shift_headings((O/'ledgers'/f'{pid}.md').read_text(),2),'',
 '</details>',
 '']
MAIN.write_text(normalize_bold('\n'.join(parts)).rstrip()+'\n')
print(MAIN,MAIN.stat().st_size)
