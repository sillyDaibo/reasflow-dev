# B 是否实际使用 Experiment Agent Skills：专项核查

**结论：B 确实使用了部分 ReasFlow Skills，并非零 Skill 的原生 Codex。** 实际形态是 Codex 执行器 + Experiment 根角色指令 + 部分被读取/执行的 Skills；不能据此说全部 Experiment Agent 能力都发挥了作用。

范围：此前报告固定的16篇、32条第003次运行root轨迹。这里重新解析实际工具输入中的cmd字符串，排除仅查找文件名、patch文本和脚本--help；统计按任务去重。轨迹输入/输出存在截断，因此以下是可观察证据下限，零记录不证明指令完全没有影响。

## Skill 使用矩阵

“读取”表示明确cat/sed等读取SKILL.md的命令记录，不等于完整遵循。“脚本”表示调用打包脚本的尝试，不把每次尝试算成功。无独立脚本的文本型Skill，读取指令本身就是其使用方式之一。

| Skill | B有明确读取命令的任务数 | B有打包脚本执行尝试的任务数 |
|---|---:|---:|
| experiment-execution | 11/16 | 0/16 |
| experiment-design | 4/16 | 0/16 |
| smart-plotting | 11/16 | 9/16 |
| knowledge-card-retrieval | 12/16 | 15/16 |
| artifact-inspection | 4/16 | 0/16 |
| auto-tuning | 0/16 | 0/16 |
| latex-report-generation | 0/16 | 0/16 |
| report-integration | 0/16 | 0/16 |

脚本统计具体覆盖knowledge-card-retrieval的search-cards.py/read-card.py及smart-plotting的smart-plot.py；其余Skill没有本轮明确的打包脚本使用证据，不能用这个0否定其文本指令作用。A的16条轨迹中没有发现这8个ReasFlow Skill的相应读取/脚本命令。B的16条均至少有上述一种Skill脚本尝试：15条有知识卡检索，剩下1904.12017有smart-plot。

## 可以确认成功的具体例子

1. RSA B先读取experiment-execution与knowledge-card-retrieval；随后执行search-cards.py，返回包括TECH-DISTRIBUTED-VARIANCE-REDUCTION在内的卡片，再用read-card.py读取该卡，工具返回真实YAML内容。这是明确的检索与读取成功。[1811.03761 B 原始L29](/Users/zanehuang/work/OptiRepro/reports/cpu30/analysis-2026-09-06/trajectory/1811.03761-B.observable.md:710)；[1811.03761 B 原始L35](/Users/zanehuang/work/OptiRepro/reports/cpu30/analysis-2026-09-06/trajectory/1811.03761-B.observable.md:726)；[1811.03761 B 原始L39](/Users/zanehuang/work/OptiRepro/reports/cpu30/analysis-2026-09-06/trajectory/1811.03761-B.observable.md:783)。

2. 2501.04443 B执行smart-plot.py，分别生成LocalSGD、SCAFFOLD与附录参数扫描图；相邻工具输出明确返回status=success、输出PNG路径、chart和series。它实际使用了打包绘图能力。[2501.04443 B 原始L358](/Users/zanehuang/work/OptiRepro/reports/cpu30/analysis-2026-09-06/trajectory/2501.04443-B.observable.md:2153)。

3. 1904.12017 B没有知识卡检索记录，但读取experiment-execution和smart-plotting，随后执行smart-plot.py处理四个实验的plot_spec。不能把“没检索知识卡”解释为“没用任何Skill”。[1904.12017 B 原始L437](/Users/zanehuang/work/OptiRepro/reports/cpu30/analysis-2026-09-06/trajectory/1904.12017-B.observable.md:2429)；[1904.12017 B 原始L473](/Users/zanehuang/work/OptiRepro/reports/cpu30/analysis-2026-09-06/trajectory/1904.12017-B.observable.md:2795)。

## 调用不一定成功，也不一定影响前期决策

2306.04961 B尝试smart-plot.py的--request/--auto-analyze路径，工具返回exit_code=1、OPENAI_API_KEY not set，随后自行用Matplotlib生成图。这属于尝试Skill后回退到通用编码，不能计作该AI绘图调用成功。[2306.04961 B 原始L613](/Users/zanehuang/work/OptiRepro/reports/cpu30/analysis-2026-09-06/trajectory/2306.04961-B.observable.md:2812)。

2501.09516 B的知识卡检索在论文实验与交付审计后期才补做；虽然返回了实际卡片，不能据此说它帮助了前期算法设计。[2501.09516 B 原始L504](/Users/zanehuang/work/OptiRepro/reports/cpu30/analysis-2026-09-06/trajectory/2501.09516-B.observable.md:3229)。

## 应怎样解释这次A/B

这里Skill不是独立模型。Codex通过exec_command读SKILL.md、运行Skill脚本，并仍使用apply_patch/exec_command等通用工具完成实现；不能仅因工具名是通用工具，就判定未使用Skill。反过来，有读取或脚本执行也不能证明Skill改善了算法保真或结果分。

32条保存root轨迹未观察到spawn_agent创建子Agent，也未看到ReaScholar适配器/域名的直接工具调用。它们与本地知识卡、打包绘图是不同功能。原报告中的“B只发挥部分工作流能力”应理解为：部分Skills明确用了，但没有证据说明多Agent、在线ReaScholar、自动调参及完整LaTeX报告链路全部被执行。

## 逐篇可观察使用

| 论文 | 明确读取的SKILL.md | 打包脚本尝试 |
|---|---|---|
| 1811.03761 | experiment-execution, knowledge-card-retrieval | read-card.py, search-cards.py |
| 1904.12017 | experiment-execution, smart-plotting | smart-plot.py |
| 2102.06704 | experiment-execution, knowledge-card-retrieval, smart-plotting | search-cards.py |
| 2111.03820 | knowledge-card-retrieval | search-cards.py |
| 2201.13320 | 未发现 | search-cards.py |
| 2207.04555 | 未发现 | search-cards.py |
| 2212.02387 | artifact-inspection, experiment-design, experiment-execution, knowledge-card-retrieval, smart-plotting | read-card.py, search-cards.py, smart-plot.py |
| 2306.04961 | knowledge-card-retrieval, smart-plotting | search-cards.py, smart-plot.py |
| 2306.05100 | experiment-execution, knowledge-card-retrieval, smart-plotting | read-card.py, search-cards.py, smart-plot.py |
| 2309.05204 | artifact-inspection, experiment-design, experiment-execution, knowledge-card-retrieval, smart-plotting | search-cards.py, smart-plot.py |
| 2310.09804 | experiment-design, experiment-execution, knowledge-card-retrieval, smart-plotting | read-card.py, search-cards.py |
| 2501.04443 | experiment-execution, knowledge-card-retrieval, smart-plotting | read-card.py, search-cards.py, smart-plot.py |
| 2501.09516 | 未发现 | search-cards.py |
| 2501.18312 | artifact-inspection, experiment-execution, knowledge-card-retrieval, smart-plotting | read-card.py, search-cards.py, smart-plot.py |
| 2503.07594 | artifact-inspection, experiment-execution, knowledge-card-retrieval, smart-plotting | search-cards.py, smart-plot.py |
| 2504.19004 | experiment-design, experiment-execution, knowledge-card-retrieval, smart-plotting | read-card.py, search-cards.py, smart-plot.py |

完整命令及相邻输出：[skill_usage_audit.json](/Users/zanehuang/work/OptiRepro/reports/cpu30/analysis-2026-09-06/trajectory/skill_usage_audit.json)。可复查脚本：[audit_b_skill_usage.py](/Users/zanehuang/work/OptiRepro/reports/cpu30/analysis-2026-09-06/trajectory/audit_b_skill_usage.py)。
