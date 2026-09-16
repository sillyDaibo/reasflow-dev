# CPU30 算法 Judge 改进与验证（2026-09-15）

本轮使用 CPU30 已完成复现的 **5 篇论文、10 个原始 workspace** 打磨流程。最终版本各运行 2 次，共 20 次；另运行 3 个未修改对照和 6 个故意改错的副本，共 29 次。原始复现仓库、论文预期及容差均未修改。

新增的独立复核、版本校验和验收判断已经实现并测试。当前能给出可追溯的有限实验结论，但尚不能据此保证整篇论文或整套代码完全正确，也没有完成 1 万篇自动处理能力的验证。

## 现在的流程

1. 只读原论文，确定核心算法、小实验输入、每步预期状态和输出。保存并冻结标准。
2. 新的论文会话独立复算、核对原文，逐个实验给出意见和范围。审核绑定到这份标准。
3. 另一个会话接收公开输入和生成的 workspace 路径，找原函数并编写外部调用脚本；看不到私有答案。
4. 再由独立会话只看公开输入、脚本和源码，检查是否忠实调用，有无重写算法或补偿错误，记录替换目标函数等范围。
5. 配置临时环境并执行原代码；检查函数确实被调用，校验运行前后仓库、标准、审核记录、脚本、公开输入和函数列表未改变。
6. 程序逐项比较数值，分别记录观测是否完整、已有差异和是否满足本次实验验收要求。

缺审核的外部材料可以诊断运行，但即使数值全部相同也暂缓验收。审核不通过或版本不匹配会停止执行。CLI 仅在 `assessment.acceptance=eligible_on_tested_scope` 时返回 0；这个字段仅用于算法实验这一项，不能单独决定整库入库。

## 独立复核做了什么

- 两名子 agent 按论文分组阅读原 PDF、检查公式，并重新写算术程序，独立复算 **793 个数值**：RSA 158、DREAM 166、ADMM 225、ProxRR/FedRR 84、BEER 160。均在原定容差内一致。
- 第三名子 agent 不读私有答案，仅核对 10 个调用脚本、公开输入、原始源码及 9 个控制副本。审核通过表示调用保真，不表示原算法正确。
- 同一名代码审查 agent 随后独立审查生产实现，使用合成反例发现并复测 4 项修复：搜索沿外部符号链接越界、执行脚本在审核后改变仍通过、未知状态被静默当成功、哈希读取异常丢失结构化结果。
- 复核并非无条件真值。ADMM 原文有公式不一致，标准明确采用 Algorithm 4.1/Eq.(5) 的解释；DREAM 多算一轮但明确返回 a^(K)，按返回值判断；固定抽样不证明抽样分布正确。
- 透明说明：ProxRR 审查 agent 读取获准的推导脚本时，意外看到了脚本内嵌的旧审查文字。因此该篇不能称为完全盲审；其结论仍有原 PDF 和新写的独立算术程序支持。

## 10 个真实仓库的最终结果

下面的“差异数”是不同的数值位置数量，不是算法缺陷数量。每个目标两次运行的逐值比较和 assessment 都一致。

| 论文 / 复现配置 | 完整观测 / 要求观测 | 数值差异 | 本次实验验收 |
|---|---:|---:|---|
| RSA / Codex | 55/55 | 75 | 暂缓 |
| RSA / ReasFlow | 27/55 | 20 | 暂缓 |
| DREAM / Codex | 36/45 | 115 | 暂缓 |
| DREAM / ReasFlow | 41/45 | 132 | 暂缓 |
| ADMM / Codex | 45/45 | 0 | 通过选定实验 |
| ADMM / ReasFlow | 45/45 | 0 | 通过选定实验 |
| ProxRR、FedRR / Codex | 24/24 | 0 | 通过选定实验 |
| ProxRR、FedRR / ReasFlow | 24/24 | 47 | 暂缓 |
| BEER / Codex | 32/32 | 0 | 通过选定实验 |
| BEER / ReasFlow | 32/32 | 4 | 暂缓 |

4 个仓库通过选定实验，6 个暂缓。RSA/ReasFlow、DREAM 的输出覆盖不足与已有数值差异现在同时展示，不会因一个“无法判断”掩盖实测差异。RSA/Codex 已有主节点使用新旧局部状态的实质差异证据；梯度平均的归一化问题不能仅凭数值差异直接称为算法错误。DREAM/Codex 的混合参数、投影顺序及共享节点抽样已有[深入审查证据](/Users/zanehuang/work/OptiRepro/reports/judge-paper-only-expanded-20260915/review-rsa-dream/REVIEW.md)。

BEER/ReasFlow 的 4 个差异很小，报告给出“精度与数学含义复查”提示。沿用此前独立诊断，它们与 float32 运算一致；本轮没有放宽既定容差、强行改成通过或称其为 4 个算法错误。详见[上一轮精度诊断](/Users/zanehuang/work/OptiRepro/reports/judge-paper-only-expanded-20260915/BEER_PRECISION_REVIEW.md)。

## 故意加入错误能否发现

控制副本在看本轮运行结果前准备，保留真实算法调用。每个错误副本仅改一处原算法语句；原 workspace 未改。未修改对照选自此前通过有限实验的三个 Codex 仓库，不构成整库正确的金标准。

| 控制副本 | 预设结果 | 实测差异数 | 是否符合预设 |
|---|---|---:|---|
| stratified-codex-positive | 匹配 | 0 | 是 |
| stratified-codex-missing_loss_dual | 发现差异 | 149 | 是 |
| stratified-codex-wrong_consensus_rhs | 发现差异 | 192 | 是 |
| proxrr-codex-positive | 匹配 | 0 | 是 |
| proxrr-codex-wrong_prox_scale | 发现差异 | 34 | 是 |
| proxrr-codex-wrong_inner_step | 发现差异 | 45 | 是 |
| beer-codex-positive | 匹配 | 0 | 是 |
| beer-codex-stale_gradient_tracker | 发现差异 | 96 | 是 |
| beer-codex-wrong_h_residual | 发现差异 | 48 | 是 |

3/3 未修改对照通过，6/6 故意错误被发现并暂缓，且观测完整。这说明这些实验能区分所设计的六种错误；不能把 6/6 外推成 Judge 在所有论文上的准确率或召回率。

## 自动化进展与剩余限制

新代码支持自动生成标准后启动独立论文复核，以及自动生成调用脚本后启动独立脚本审核，均为独立会话。外部审核可作为缓存复用，但必须与文件内容匹配，不需要人工逐篇编写二元 rubric。

**论文标准沿用前轮子 agent 的准备产物，本轮由新的 Codex 子 agent 重新复核；执行回放未调用独立模型 API，也未使用 API key。** 模型会话之间的数据隔离和验收路径有模拟客户端测试；自动调用外部 API 的全链路、失败重试成本及陌生论文通过率，本轮没有实测，不能称为已解决。manifest 现在如实记录无 API 回放的 `model: null`。

仍需进一步验证：未参与调试的论文是否也能自动生成可信标准和忠实调用脚本；一篇中的未覆盖机制、实际数据路径、随机分布、长时间行为及实验结论；论文歧义和低精度实现的自动处理。原函数调用追踪不是对恶意脚本的安全隔离，外部审查记录的哈希也不能证明审查者诚实或真正独立。

下一步适合固定当前流程，再选择 CPU30 中未参与本轮调试的论文做独立验证，统计标准审核失败、脚本审核失败、环境失败、覆盖不足和数值差异各自比例及成本。达到可接受水平后再接小批量语料库；保留人工抽查，而非为每篇手工写 rubric。

## 证据与复跑

- 最终实测：/Users/zanehuang/work/OptiRepro/reports/judge-hardening-cpu30-20260915/validation/20260915T115657345079Z/summary.json
- 版本记录：/Users/zanehuang/work/OptiRepro/reports/judge-hardening-cpu30-20260915/validation/20260915T115657345079Z/CODE_SHA256.json
- 独立论文审核：/Users/zanehuang/work/OptiRepro/reports/judge-hardening-cpu30-20260915/paper_reviews
- 调用脚本审核：/Users/zanehuang/work/OptiRepro/reports/judge-hardening-cpu30-20260915/adapter_reviews
- 控制副本及修改说明：/Users/zanehuang/work/OptiRepro/reports/judge-hardening-cpu30-20260915/controls/manifest.json
- 代码审查与修复反例：/Users/zanehuang/work/OptiRepro/reports/judge-hardening-cpu30-20260915/IMPLEMENTATION_REVIEW.md
- 单元/集成回归：105 passed；命令 `/tmp/optirepro-paper-judge-20260915/bin/python -m pytest tests -q`，工作目录 `repo_judge`。
- 初始运行保存在 validation.log 对应批次，期间实现继续修复，仅供调试；本报告统计仅来自上述代码版本保持不变的最终批次。

```bash
/tmp/optirepro-paper-judge-20260915/bin/python reports/judge-hardening-cpu30-20260915/run_validation.py --workers 4 --repeats 2
```
