# RSA / DREAM Codex 原生实现：论文与代码再次复核

本次直接重读原 PDF 的算法公式，并检查原始代码、当前适配器与最终五篇评测批次的真实观察。RSA 视觉核对 PDF 第 4 页 Algorithm 2 / Eq.(10)(11)，并核对第 3 页 Eq.(7)(8)文字；DREAM 视觉核对第 3 页 Algorithm 1 与第 6 页 Algorithm 2。此复核涉及核心算法执行路径，不是整个仓库所有功能的完整审计。没有修改论文标准、适配器、被测源码或原有判定。

结论：两个 Codex 原生实现均存在与原论文核心算法明确不一致的行为；这不是由“没有跑出结果”或“缺少返回字段”单独推断的。但不能把所有数值差异等价当作算法错误，RSA 的归一化差异尤其需要收紧前述表述。

## RSA：明确的更新时点差异

论文 Algorithm 2 要求每个工作节点发送旧状态 x_i^k，随后更新自己的状态；主节点用这些旧状态计算 x_0^(k+1)。Eq.(8)(11)与此一致。

[原代码 rsa.py](/Users/zanehuang/work/OptiRepro/reports/cpu30/analysis-2026-09-06/evidence/OptiRepro_cpu/agent_reproduction/runs/1811.03761/Codex原生-完整复现-Goal/第003次运行/workspace/rsa_repro/rsa.py:53) 先生成 next_local，再在第 55 行令 received=next_local.copy()，第 63–65 行让主节点使用这些新状态。因此算法从论文的共同使用旧状态变成了工作节点先更新、主节点再依赖新状态更新。这不是变量改名；它能改变符号惩罚的方向。

最终批次第一个 l1 小实验：主节点首坐标预期 0.875，实际 0.625；差 0.25，远大于容差。原本为 1.2 的工作节点首坐标在更新后变成约 0.8083，跨过主节点的 1，使对应符号项反转。实际初态、梯度输入及主节点观察位置已与适配器核对。

[最终实测结果](/Users/zanehuang/work/OptiRepro/reports/cpu30/analysis-2026-09-06/evidence/OptiRepro_cpu/agent_reproduction/runs/1811.03761/Codex原生-完整复现-Goal/第003次运行/judge/evaluations/paper-expanded-20260914T170835142095Z-1/algorithm/result.json)。

## RSA：不能把梯度缩放孤立地当作已证明的算法错误

第 53 行还把目标函数梯度除以 workers。给定本次独立实验所定义的本地目标函数，这与冻结标准不一致，相关数值差异是真实的。

但 [README](/Users/zanehuang/work/OptiRepro/reports/cpu30/analysis-2026-09-06/evidence/OptiRepro_cpu/agent_reproduction/runs/1811.03761/Codex原生-完整复现-Goal/第003次运行/workspace/README.md:59) 明确声称该缩放沿用参考实现。论文的本地目标函数可以有不同归一化约定；如果软件接口将输入梯度解释为未归一化损失，而实际被优化的 F_i 是其除以节点数后的量，就不能只看到 `/ workers` 就宣布算法必然错误。还需统一整体目标函数、正则项、惩罚系数与步长的含义。本次没有另外核实官方仓库，所以 README 的说法仅作为其设计意图证据。

因此：保留此项“在本实验目标定义下不一致”的事实；收紧此前将其直接叙述为独立算法错误的表述。RSA 更坚实的算法不一致证据是上一节的更新时点问题。

## DREAM：与缺失输出无关的核心差异

### 1. FastMix 系数不同，初始化就已出现差异

论文第 3 页 Algorithm 1 的系数是 1/(1+sqrt(1-lambda_2(W)^2))。当第二特征值是 0.8 时，其值为 0.625。

[原 mixing.py](/Users/zanehuang/work/OptiRepro/reports/cpu30/analysis-2026-09-06/evidence/OptiRepro_cpu_2/agent_reproduction/runs/2212.02387/Codex原生-完整复现-Goal/第003次运行/workspace/dream_repro/mixing.py:37) 第 43 行使用 (1-q)/(1+q)，其中 q=sqrt(1-sigma^2)，本例得到 0.25。矩阵、初始梯度和一轮混合的输入已核对一致；最早 tracker 首坐标预期 3.0875，实际 3.125。此时尚未进入迭代随机分支，不能归因于抽样序号或输出接口。

论文伪代码的循环上界和返回下标存在多算一个未返回状态的写法；冻结标准取其明确返回的 a^(K)。该写法不影响上述系数公式和 K=1 返回值的比较。

### 2. 约束处理与节点混合顺序颠倒

论文第 6 页 Algorithm 2 第 12 行先对每个节点的 y 更新做投影，再 FastMix；即先把越界数值拉回允许范围，再进行节点间加权合并。

[原 algorithms.py](/Users/zanehuang/work/OptiRepro/reports/cpu30/analysis-2026-09-06/evidence/OptiRepro_cpu_2/agent_reproduction/runs/2212.02387/Codex原生-完整复现-Goal/第003次运行/workspace/dream_repro/algorithms.py:128) 第 129–130 行及第 137–138 行先 FastMix，再投影。投影是非线性操作，一般不能与加权合并交换顺序。这是实际计算顺序不同；适配器没有补造论文要求但原代码不存在的“混合前投影后”状态。

### 3. 每节点的更新抽样被替换为全局共用抽样

论文第 18 行在各节点的并行循环内分别采样 omega_t(i)。[原 algorithms.py](/Users/zanehuang/work/OptiRepro/reports/cpu30/analysis-2026-09-06/evidence/OptiRepro_cpu_2/agent_reproduction/runs/2212.02387/Codex原生-完整复现-Goal/第003次运行/workspace/dream_repro/algorithms.py:139) 只读取节点 0 的一次随机结果，随后令所有节点一起更新或一起跳过。

冻结实验首步指定节点 0 更新、节点 1 跳过。实际节点 1 仍更新；这与原分支直接对应。这里不能混淆论文第 10 行的全局 refresh 随机量 zeta 与第 18 行的每节点 omega。

[最终实测结果](/Users/zanehuang/work/OptiRepro/reports/cpu30/analysis-2026-09-06/evidence/OptiRepro_cpu_2/agent_reproduction/runs/2212.02387/Codex原生-完整复现-Goal/第003次运行/judge/evaluations/paper-expanded-20260914T170835142095Z-1/algorithm/result.json)。其总体状态为无法完整判定，因为还缺历史候选/随机输出和某些必要观察；该状态不撤销已经有证据的局部算法差异。

## 对 Judge 合理性的判断

原论文独立出题、先冻结过程与答案、另一个会话调用代码、最后程序比较的方向合理。现有结果已具备寻找具体问题的能力，但目前不能把一个总状态或超差数字数量直接当作论文复现配置的最终排名。

至少应把两个判断分开记录：一是规定实验是否全部完成、覆盖了多少机制；二是已经观察到的部分是否存在明确算法错误、仅有归一化约定差异或浮点精度差异。DREAM 缺少输出但已有算法错误，就是两者不能混为一谈的例子。

适配器同样需要被审查：输入含义、梯度缩放、状态采集时点和矩阵方向都会影响结论。历史 DREAM 适配器曾采错观察位置，已经纠正并重跑；当前上述 FastMix 首个差异与投影/抽样的源码证据不依赖旧的错误观察字段。

三次结果一致证明固定实验可以重复，不能证明论文解释、输入映射或适配代码永远正确。现阶段可以用 Judge 辅助定位实现问题；用于大规模自动验收和配置排名之前，还需完善这些分类与预先约定的精度规则。
