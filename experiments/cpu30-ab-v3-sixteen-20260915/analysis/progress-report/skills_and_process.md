## 4. ReasFlow Agent 到底发挥了什么作用

### 4.1 可以确认：B 实际使用了部分 Skills

需要区分四层：配置中提供了能力；Agent 读取了技能指令；执行了技能脚本；返回结果显示调用成功。前三层都不能自动证明该能力提高了论文复现质量。文本型 Skill 没有独立脚本时，读取指令也是使用方式之一。

| Skill | B 有明确读取指令命令的论文数 | B 有脚本执行尝试的论文数 | 当前能确认到哪一步 |
| --- | ---: | ---: | --- |
| experiment-execution | 11/16 | 0/16 | 多篇明确访问实验执行指令；没有单独脚本记录不能否定文本指令的作用 |
| experiment-design | 4/16 | 0/16 | 部分论文明确访问实验设计指令；是否改变了具体方案需结合过程判断 |
| artifact-inspection | 4/16 | 0/16 | 存在产物检查指令读取；不能据此认定最终科学检查充分 |
| knowledge-card-retrieval | 12/16 | 15/16 | 多篇调用知识卡脚本；RSA 有成功检索与读取卡片的直接输出 |
| smart-plotting | 11/16 | 9/16 | 有成功绘图，也有尝试失败后回退的案例 |
| auto-tuning | 0/16 | 0/16 | 未观察到独立读取或脚本调用，不能认定自动调参流程已实际发挥作用 |
| latex-report-generation | 0/16 | 0/16 | 未观察到独立使用证据 |
| report-integration | 0/16 | 0/16 | 未观察到独立使用证据 |

这里按论文去重，脚本尝试排除了只查看 `--help`，但不把尝试都算作成功。保存事件存在截断，因此统计是可观察证据下限。A 的对应轨迹中没有发现这八项 ReasFlow Skill 的读取或脚本执行记录；B 的每篇都至少出现一种上述技能脚本尝试。[专项核查依据](/Users/zanehuang/work/OptiRepro/reports/cpu30/analysis-2026-09-06/trajectory/B_SKILL_USAGE_AUDIT.md)

### 4.2 四个案例说明“用了”之后还要判断什么

**RSA：知识获取这一步实际成功了。** B 读取实验执行和知识卡技能，运行搜索脚本获得包括分布式方差缩减卡片在内的结果，再运行读取脚本获得卡片正文。这说明检索链条不是空配置。但现有证据没有把某条卡片建议与后续关键算法修复建立明确联系，因此不能把 RSA 的成功全部归因于知识卡。[检索结果](/Users/zanehuang/work/OptiRepro/reports/cpu30/analysis-2026-09-06/trajectory/1811.03761-B.observable.md:726)、[读取卡片](/Users/zanehuang/work/OptiRepro/reports/cpu30/analysis-2026-09-06/trajectory/1811.03761-B.observable.md:783)

**2501.04443：绘图能力实际完成了工作，核心科学优势仍未复现。** B 调用 `smart-plot.py`，返回成功及图表输出；同一运行报告又明确指出固定步长下 LocalSGD、SCAFFOLD 没有优于 MbSGD。这意味着技能有可验证的产物贡献，但绘图成功本身并不解决算法协议或优势验证问题。[绘图调用与成功输出](/Users/zanehuang/work/OptiRepro/reports/cpu30/analysis-2026-09-06/trajectory/2501.04443-B.observable.md:2153)、[该篇结果分析](/Users/zanehuang/work/OptiRepro/reports/cpu30/analysis-2026-09-06/papers/2501.04443.md)

**IRLS：尝试 Skill 后回退到了通用实现。** B 尝试智能绘图的请求路径，因缺少所需 API 配置返回失败，随后自行用 Matplotlib 生成图。这里可以确认尝试和回退，不能把该次调用标为成功，也不能据此解释 IRLS 的算法失败。绘图问题和加权子问题求解偏差属于不同环节。[调用失败与后续操作](/Users/zanehuang/work/OptiRepro/reports/cpu30/analysis-2026-09-06/trajectory/2306.04961-B.observable.md:2812)

**ManPQN：技能使用发生的阶段限制了对其作用的解释。** B 的知识卡检索发生在实验和交付审计的后期。即使检索获得了内容，也不足以支持“知识卡帮助设计了前面的算法与实验”。要判断技能改善了什么，必须追踪它是否改变后续实现或实验，而不只记录调用存在。[后期知识卡使用](/Users/zanehuang/work/OptiRepro/reports/cpu30/analysis-2026-09-06/trajectory/2501.09516-B.observable.md:3229)

### 4.3 完整 ReasFlow 能力还没有在这批中得到验证

保存的根轨迹中未观察到 `spawn_agent` 创建子 Agent，也未观察到在线 ReaScholar 适配器或域名的直接工具调用。配置中注册子角色、允许在线服务，与实际执行这些流程需要分别判断。本地知识卡检索也不能替代在线论文检索能力的验证。

因此，当前 B 最准确的描述是：**Codex 承担核心执行，ReasFlow 提供实验角色与部分实际使用的技能；已经看到知识获取、实验组织和绘图等行为，但没有证据确认完整多角色流程被执行，也没有证明这些增强使总体科学结果更好。**

这对项目的启示是，后续每项 Skill 应有具体任务目标。例如实验设计 Skill 是否减少了基线遗漏，产物检查 Skill 是否发现目标与梯度不一致，知识卡是否帮助恢复了正确的算子。这样的证据比单纯提高技能使用覆盖更能解释其价值。

## 5. Trace / Trajectory 如何解释最终结果

本文使用公开进度、实际工具输入输出和交付产物还原执行过程。Agent 的公开解释可以说明它当时声称在做什么；是否确实修好，则需要最终代码与结果支持。

### 5.1 能发现问题并重跑，是已经展示的能力

RSA A 的过程是：发现像素被归一化，与官方协议不符，修正后重跑；再发现攻击错误地施加给所有 worker，修正攻击范围；随后统一方法之间的随机批次以改善比较口径。最终异构任务中 RSA 显著优于若干鲁棒聚合基线。这串过程比“Agent 最后说完成了”更有说服力，因为它包含具体错误、代码方向和后续实验。但最后仍有同步更新约定与论文不完全一致的问题，所以这也不是整体正确的证明。[数据尺度纠正](/Users/zanehuang/work/OptiRepro/reports/cpu30/analysis-2026-09-06/trajectory/1811.03761-A.observable.md:187)、[攻击语义纠正](/Users/zanehuang/work/OptiRepro/reports/cpu30/analysis-2026-09-06/trajectory/1811.03761-A.observable.md:199)、[统一随机流](/Users/zanehuang/work/OptiRepro/reports/cpu30/analysis-2026-09-06/trajectory/1811.03761-A.observable.md:211)

SCAFFOLD B 在首次实验后发现采样方式与官方实现不同，改为无放回采样并重跑；最终又把“所有检查点都领先”的陈述收窄为“全部终点领先、部分检查点例外”。它同时展示了实现修正和结论范围修正，这两种能力都与可信算法库有关。[SCAFFOLD B 的复核过程](/Users/zanehuang/work/OptiRepro/reports/cpu30/analysis-2026-09-06/trajectory/2503.07594-B.observable.md:239)

### 5.2 执行过程中缩小实验，会改变“完成”的含义

IRLS B 将较简单的 baseline 升级为更接近官方的 SPF 交替 HTP 后，实验成本提高，随后缩小 phase-transition 网格。此时，baseline 的局部改进与论文覆盖的退步同时发生。最终“有完整实验目录”只能说明完成了缩减后的任务，不能说明原论文相变主张已完整检查。[IRLS B 的范围调整](/Users/zanehuang/work/OptiRepro/reports/cpu30/analysis-2026-09-06/trajectory/2306.04961-B.observable.md:223)

ManPQN B 修正实现后，用更小预算重新生成与最终配置一致的结果。这改善了交付的一致性，但不会自动补回未跑的论文网格。对于算法库，必须同时保存“实际做了什么”和“原论文要求什么”，否则后续使用者会把缩减后的任务误当完整复现。[ManPQN B 的修订过程](/Users/zanehuang/work/OptiRepro/reports/cpu30/analysis-2026-09-06/trajectory/2501.09516-B.observable.md:191)

### 5.3 多轮自查和充分运行，仍可能留下核心错误

DREAM B 从较短实验增加到更完整的轮数与多种子运行，也检查了数据尾部处理；最终核心优势仍未出现。源码复核发现目标与梯度尺度不一致、FastMix 二阶递推有偏差。现有证据说明，“实验跑得更完整”与“实现核心机制正确”是两个维度。应先用公式级检查排除这类错误，再解释增加预算后的结果。[DREAM B 的公开进度](/Users/zanehuang/work/OptiRepro/reports/cpu30/analysis-2026-09-06/trajectory/2212.02387-B.observable.md:455)、[公式与源码核查](/Users/zanehuang/work/OptiRepro/reports/cpu30/analysis-2026-09-06/papers/2212.02387.md)

后面的每篇章节均保留 A/B 关键执行过程和对应轨迹入口。它们用于解释结果形成的原因，而不以轨迹长度或工具调用总量评价能力。
