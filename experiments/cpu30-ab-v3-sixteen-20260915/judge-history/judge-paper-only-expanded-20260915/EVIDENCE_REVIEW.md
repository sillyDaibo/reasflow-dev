这次既出现完整通过，也出现可定位的算法差异和需要谨慎解释的精度差异。标准在读取实现之前冻结；没有依据运行结果更改输入、预期或允许误差。

### ADMM：完整主循环的通过证据

两个实现均调用原有完整 ADMM 入口，执行 4 轮，观察第 1、2、4 轮的五组状态。三种输入包括带相关性的二维二次损失、缺少本地数据的节点与 l1 正则，以及 Poisson 损失。每个仓库共检查 225 个数值。二次损失、Poisson 和 ridge 原语来自已有代码；Codex 缺少 l1 原语，因此该用例通过公开问题输入的 prox 回调提供 l1。通过结论不涵盖“Codex 已内置 l1 实现”，也不涵盖停止条件或自适应罚参数。

图方程、双变量更新和原有数值求解器都保留。公开输入直接给定图矩阵，并明确采用论文 Algorithm 4.1 / Eq.(5)，避免原文另几处符号不一致影响测试。约定由论文 Agent 在看实现之前确定。

### ProxRR / FedRR：通过与明确的错误对照

Codex 原生在三个用例上完整匹配。ReasFlow 的二次 ProxRR 用例通过；logistic 用例有 21 个数值差异，不等样本量 FedRR 用例有 26 个数值差异。这些是后续状态的连锁影响，主要对应两处具体行为：

- [ReasFlow 梯度实现](/Users/zanehuang/work/OptiRepro/reports/cpu30/analysis-2026-09-06/evidence/OptiRepro_cpu_2/agent_reproduction/runs/2102.06704/ReasFlow实验Agent-完整复现-Goal/第003次运行/workspace/rr_prox_fed/losses.py:53) 在每个样本梯度中加入 `lambda2*x`，而 [原 ProxRR 驱动](/Users/zanehuang/work/OptiRepro/reports/cpu30/analysis-2026-09-06/evidence/OptiRepro_cpu_2/agent_reproduction/runs/2102.06704/ReasFlow实验Agent-完整复现-Goal/第003次运行/workspace/rr_prox_fed/methods.py:44) 在轮末仍对同一个 l2 系数做 prox。第一个样本更新首坐标：预期 0.6775063797180969，实际 0.6175063797180969；差 0.06 恰好等于公开输入 `0.25*0.4*0.6`。第二坐标差 0.02 同样对应被额外加入的项。适配器没有去掉这项。
- [ReasFlow 联邦驱动](/Users/zanehuang/work/OptiRepro/reports/cpu30/analysis-2026-09-06/evidence/OptiRepro_cpu_2/agent_reproduction/runs/2102.06704/ReasFlow实验Agent-完整复现-Goal/第003次运行/workspace/rr_prox_fed/federated.py:40) 对每客户端平均样本量做 `round`。本例 N/M=2.5，被取整成 2，prox 系数变成 0.25，而论文推演系数为 0.3125。首轮 local endpoints 和平均值全部匹配，首坐标平均值是 1.158203125；最终实际为 1.0072916666666667，预期为 0.9746621621621622，最早差异恰在服务器 prox。没有把问题错误归到客户端更新或平均方式。

ProxRR 的三个不同步长通过原有 `epochs=1` 和 `x0` 接口逐轮调用，每轮执行的内部更新及 prox 全部来自原驱动。它验证原算法单轮与状态传递，不验证仓库自带的完整步长调度策略。FedRR 直接运行原完整三轮驱动。

### BEER：避免把微小精度差异当作算法缺陷

Codex 原生完整运行两个三轮用例，X/H/V/G 共 160 个数值全部符合冻结标准。ReasFlow 的第二个用例完整匹配；第一个用例仅第 3 轮 V/G 的 4 个数值超过原定容差，绝对差在 8.49e-8 至 1.93e-7 之间。原实现使用 float32，而论文推演使用精确有理数。

严格比较结果保留为“数值不一致”，不能直接解释为四个算法错误。[独立精度审查](/Users/zanehuang/work/OptiRepro/reports/judge-paper-only-expanded-20260915/BEER_PRECISION_REVIEW.md) 按论文递推及源码明确的舍入位置独立计算，精确复现了 160/160 个实际值；采用 float64 的诊断与冻结标准最大差为 4.44e-16。证据支持将这四处归为精度标记，而非当前轨迹的数学更新错误。没有事后放宽容差、提高原代码精度或把结果改成通过。

两个适配器分别调用原完整实验驱动，并注入公开的目标函数、初态、图与压缩算子；因此本次通过范围是给定压缩算子下的核心更新，不是已有压缩器实现或通信编码的完整验收。ReasFlow 把 X/H 与 V/G 错开更新，采集位置已按公开状态时点对应，不把错开存储本身视作错误。

### RSA / DREAM 复测

原两篇使用已冻结标准重新运行，保留上一轮发现的梯度归一化、主节点消息时点、混合系数差异及无法完整观察的情况。具体源代码与独立复核见 [上一轮证据审查](/Users/zanehuang/work/OptiRepro/reports/judge-paper-only-20260915/INDEPENDENT_EVIDENCE_REVIEW.md)。本轮未修复被测算法或修改旧标准。

### 扩大测试发现并修复的 Judge 问题

初次新增 ProxRR 集成被误报为“没有调用原算法”：适配器声明 `Class.method`，旧调用记录只保存 `method`。现在按源代码位置识别完整所属类，仍兼容已有简单函数名；新增测试确认另一类的同名方法无法冒充目标方法，并覆盖 Python 3.9、类方法及同源码安装副本。

另补齐了新虚拟环境需要安装的依赖记录，不能把手工试运行环境里已安装的包当作正式新环境也具备。初次集成记录保留在 validation/；最终报告只采用修复后对全部 10 个目标重新执行的统一批次。

这些结果表明，算法更新检查已经能区分通过、明显计算差异和无法完整测试。但如果要据此自动给复现配置排名，仍需在出题阶段预先统一数值精度与误差规则；本次的 BEER 精度案例不能与 ProxRR 的机制错误等价计分。
