# 独立实测证据复核

本次复核只读检查冻结论文契约、外部 adapter、真实 workspace 算法，以及 `validation/20260914T162349Z/summary.json` 中每个 target 的 repeat 1 数值检查与观察记录。没有修改原契约、预期数值或 workspace。复核目标是区分原实现差异、输入与观察适配错误、接口缺项，避免仅凭失败数值数量归因。

**本报告复核的是 DREAM adapter 修正前的记录。** 已识别的原生 `pre_projection` 映射和两库缺项报告正在单独修正；DREAM 的最终状态、检查数量与逐项数值应以修正后重新执行产生的不可变报告为准。下述源码定位与早期 `g/s/z` 归因不依赖这些输出字段的修正。

## 证据定位

冻结契约：

- `papers/1811.03761/contract.json`，摘要 `2727bb440954babcab3c3ada9270b7927b3d2bcb074976c9c9167a921fc75355`。
- `papers/2212.02387/contract.json`，摘要 `b3016687a92c81b6f373d898e369ea9a0eb3f90392fd150b2cec3adc9a924fb3`。

各 target 的真实 workspace 和本次 repeat 1 结果绝对路径均保存在上述 summary 的对应行。下文源码行号相对于这些 workspace；数值依据为对应结果旁的 `comparison/checks.json` 与 `comparison/observations.json`。所有路径均以本报告所在目录为报告材料的相对根。

## RSA codex：首步差异具有明确源码依据

三个 case 的初始 master、regular workers，以及第一步的原始梯度 callback 返回、worker 范数子梯度、Byzantine master 子梯度与冻结契约匹配。adapter 将给定二次目标、外部攻击消息和原生 `rsa_step` 的独立状态参数对应起来，没有发现初值、worker 编号或攻击消息的错位。

`rsa_repro/rsa.py:53` 在 `softmax_gradient` 返回之后另除以总 worker 数 3。原始 `softmax_gradient` 自身按本地样本数返回平均损失梯度；adapter 在该目标函数边界返回公开二次函数的梯度，明确保留 core 内部的 `/ workers`。

在 l1 case 第一步，第一个 worker 的第一坐标因此为：

```text
实际：1.2 - 0.25 × (3.2 / 3 + 0.5) = 0.8083333333333333
契约：1.2 - 0.25 × (3.2 + 0.5)     = 0.2749999999999999
```

这说明在本次声明的目标 callback 边界下，原实现实际使用的局部梯度缩放与契约不同。`worker_loss_gradients_before_update` 当前记录的是 callback 的原始返回，不能据该字段通过便称“实际更新所用梯度已经匹配”；内部缩放要结合源码和后续状态解释。

`rsa_repro/rsa.py:55` 将 `next_local` 复制为发送消息，随后第 63–64 行用这些已经更新的 regular worker 消息计算 master penalty。冻结契约要求 master 和 workers 均使用旧状态同步更新。l1 case 第一步的首坐标 penalty 因此从预期 `-1` 变为实际 `+1`，master 第一坐标从预期 `0.875` 变为实际 `0.625`。这些值直接对应原代码执行结果，没有使用 adapter 自行重建的 master 更新。

## RSA ReasFlow：步长接口限制需要单独保留

原 `run_training` 固定使用 `alpha0 / sqrt(step + 1)`，不能表示冻结契约中的完整显式步长表。adapter 只执行匹配的初始前缀，未重置训练循环、覆盖局部 alpha 或合成余下轨迹。因此缺失的后续观察应保留为接口不支持，不能把整条 case 的缺失计入算法数值错误。

前缀中也观察到与 RSA codex 相同类型的额外梯度缩放和已更新消息聚合差异，但这不能使未执行的后续步骤获得结论。修正前 summary 将该 target 归为 `INCONCLUSIVE / CASE_INTERFACE_UNSUPPORTED`，与已声明限制相符。

## DREAM 两库：最早分歧在 FastMix，发生在随机输入之前

两个 case、两个实现的 step 0 `z` 与 `g` 均在容差内匹配。由此确认初始缓冲区、agent/component 分区、公开二次目标及完整梯度均值的输入对应正确。adapter 每次调用 FastMix 时还检查实际生成的矩阵与公开 `W` 相同。

最早差异是 step 0 的 tracker `s`，此时尚未消费迭代中的 Bernoulli 或抽样输入，因此不能归因于随机序号错位。

公开矩阵的第二特征值为 `0.8`，对应 `sqrt(1 - sigma²) = 0.6`。冻结契约使用的 FastMix 系数为 `1 / (1 + 0.6) = 0.625`；两库实际使用 `(1 - 0.6) / (1 + 0.6) = 0.25`：

- 原生：`dream_repro/mixing.py:37–43`。
- ReasFlow：`src/dream_reproduction/mixing.py:39–42`。

第一个 case 的初始 `g` 第一列为 `[3.25, 2.25]`。该系数差异精确解释两库实际 `s[0,0] = 3.125`，冻结契约为 `3.0875`。

ReasFlow 还有独立的递推状态保存问题：`src/dream_reproduction/mixing.py:44–47` 每轮计算新的 `current` 后，将 `previous` 也设为新的 `current`，没有保留该轮更新之前的状态。第二个 case 中 `K0 = 2`，首个 tracker 坐标如下：

| 来源 | step 0 的 s[0,0] |
| --- | ---: |
| 冻结契约 | -0.434375 |
| 原生，旧状态保存正确但系数不同 | -0.125 |
| ReasFlow，系数不同且旧状态保存错误 | -0.046875 |

这些早期差异已有输入和源码证据。后续 `z/g/s` 的许多数差是其传播结果，不能逐值当作新的独立缺陷。

## DREAM：首步随机流及梯度递推复核

复核使用真实观察到的 step 0/1 `z`、公开 sample indices 和二次目标系数，独立计算应由这些实际状态产生的梯度差，仅用于事后诊断，没有反馈给算法或改变预期。

第一个 case 指定首步 active 为 `[1, 0]`。

- 原生 node 0 的实际 `g1 = [2.9921875, 0.7421875]`，精确等于所指定 sample 0 的梯度差除以 q 再加 g0。
- 原生 node 1 的实际 `g1 = [-0.5312500000000009, -1.4921875000000004]`，精确等于所指定 sample 1 的更新值，尽管该节点被指定跳过。
- ReasFlow node 0 的实际 `g1 = [2.8671875, 0.9921875]`，符合其实际 z 与指定样本的递推。
- ReasFlow node 1 正确保持 `g1 = [2.25, -1.5]`。

原生 `dream_repro/algorithms.py:139–144` 只读取 node 0 的一次 recursive 门控，然后更新所有节点。这不能消费公开契约中不同节点的独立 active 输入；adapter 没有为它补充节点门控或更改分支。该现象对应原实现机制的缺失，并非 adapter 随机数消费序号错误。

ReasFlow 的首步梯度递推与跳过行为在给定实际 z 下均正确。它相对冻结轨迹的首步 g 差异由先前 FastMix 的 s/z 差异传递，不应再宣称该证据证明其 q 缩放、样本选择或 batch averaging 错误。

## 必须修正的观察语义与接口报告

### 原生 pre_projection 的观察映射

修正前的 `adapters/dream/native/adapter.py` 用 `loc['x_new']` 作为 `pre_projection` 和 `projected` 的 x 列；此时 x 已经混合。冻结契约的 `pre_projection` 表示原始 descent/ascent 输入，处于混合之前，二者不是同一观察语义。

真实未混合的更新输入已经在该步前两次 FastMix 的入参中被只读捕获，可以据此修正 `pre_projection`，无需重算更新或改变算法。原生代码的 y 投影实际发生在混合之后；若契约要求的混合前 projected 状态在原执行中没有相应操作，就应报告该观察不支持，不能把另一位置的投影输出改名后比较，也不能构造未发生的操作。

因此修正前部分 `pre_projection/projected` 的数差包含观察语义不一致，不应全部叙述为独立算法数值错误。原实现投影与混合顺序本身的差异仍可结合真实代码和最终 z 讨论。

### 两库 output_candidates 与 x_out 缺项

修正前两库各有四个协议错误：两个 case 分别缺 `output_candidates` 和 `x_out`。原函数返回指标 history，没有构造契约规定的历史 x 候选集合，也没有按给定历史随机索引返回 x。

adapter 不应通过事后组合观察或随机选择来补写原算法没有执行的输出步骤。但这是已识别的接口缺项，应在结构化 case 中明确 `status=blocked` 与 reason，归入 `INCONCLUSIVE / CASE_INTERFACE_UNSUPPORTED`；修正前只在 stderr 解释缺项，导致总体 `RUN_FAILED / INVALID_OBSERVATIONS`，混淆了接口限制与意外损坏输出。

这两项 adapter 修正及随后的 DREAM 重测正在进行。最终报告必须引用新结果，不能沿用修正前的状态和数量。

## 结论边界

修正前每次 RSA codex 的 75 个、DREAM 原生的 134 个和 DREAM ReasFlow 的 132 个数值不符，均是失败数值数量，**不是独立算法问题数量**。它们包含早期错误传播、多个坐标、多个时间点，以及上述 DREAM 观察语义差异。

三次重复结果相同仅说明在给定适配、输入与运行条件下具有重复性，不能替代输入边界和观察语义审查。本复核确认了具有源码支撑的早期机制差异，也明确保留了接口限制和需修正的 adapter 观察问题；结论范围仅限这些冻结的论文算法 case，不扩展为整库质量、完整论文复现或随机分布正确性的结论。
