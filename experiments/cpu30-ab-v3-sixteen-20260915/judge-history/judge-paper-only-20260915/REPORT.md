# 算法 Judge 改造与 CPU30 实测记录

日期：2026-09-15（Asia/Shanghai）。这是新增的算法运行检查；原有静态 rubric Judge 的评分逻辑未在本次任务中改动。

## 已实现的流程

原论文 → 独立提取核心算法与小实验 → 推演并保存过程/输出 → 公开输入交给另一个会话 → 调用原 workspace 算法 → 程序逐值比较。

- 论文生成函数只有论文文本、文件哈希、论文编号与模型参数，没有 workspace 参数或仓库工具。保存预期后才开始仓库读取。
- 公共输入只包含输入、参数、机制说明以及观察点的步骤/名称/形状；不传预期数值或推导。
- 适配会话可以查源码、设置合成目标函数/初态/随机输入，并收集真正执行的中间状态；不能修算法更新或补偿错误。
- 比较由程序执行，核验全部观察、数组形状和容差，拒绝 NaN、重复、缺失及自报“通过”。核对原始算法调用与 workspace 内容完整性。
- 每次评测有独立 runtime 目录，保留论文、私有预期、适配脚本、安装动作、真实调用、实际观察和每个数值的差异。同一 evaluation 的 algorithm 目录不得覆盖。
- 环境失败、数值不一致、接口不足和观察损坏分别记录；不对数值失败自动重试或修改标准。

## 独立准备方法

两个从零上下文启动的论文 Agent 分别只阅读 RSA（1811.03761）和 DREAM（2212.02387）的原始 PDF，视觉核对公式页，并通过独立算术脚本推演。RSA 建立3个实验、55项预期观察，DREAM 建立2个实验、45项预期观察。预期契约均在适配 Agent 工作前冻结。

另两个独立适配 Agent 只读取公开输入和目标 workspace，不读取私有契约、论文推导或已有评测答案。初态、目标函数、Byzantine消息、随机输入和可行域属于明确的实验输入边界；算法的更新、除法、门控、混合顺序保持原样。另一个 Agent 复核具体数值差异与源码对应关系。

这些是原算法内核的小实验，不是原数据集完整训练。尤其硬编码模型需要目标函数边界注入时，不能把结果解读成整库运行验收。

## 最终实测结果

目标为 CPU30 历史 runs 的本地完整 workspace 镜像：RSA 和 DREAM 各自的 Codex 原生、ReasFlow 第003次运行。来源路径保留在每次评测及 FINAL_SUMMARY.json 中；没有声称检查当前远程服务器的最新状态。

每个 workspace 重复3次，共12次最终采用的实测。重复使用同一份冻结论文标准，实际执行并采集原算法输出；没有用假模型生成“通过”结论。

| 目标 | 完整实验结论 | 已观察到的数值差异数 | 三次复测一致 | 首次结果 |
|---|---|---:|---:|---|
| RSA / Codex 原生 | 数值不一致（完整观察） | 75 | 3/3 | [结果](/Users/zanehuang/work/OptiRepro/reports/cpu30/analysis-2026-09-06/evidence/OptiRepro_cpu/agent_reproduction/runs/1811.03761/Codex原生-完整复现-Goal/第003次运行/judge/evaluations/paper-only-20260914T162349Z-1/algorithm/result.json) |
| RSA / ReasFlow | 无法完整判定：固定步长无法表达规定输入 | 20 | 3/3 | [结果](/Users/zanehuang/work/OptiRepro/reports/cpu30/analysis-2026-09-06/evidence/OptiRepro_cpu/agent_reproduction/runs/1811.03761/ReasFlow实验Agent-完整复现-Goal/第003次运行/judge/evaluations/paper-only-20260914T162349Z-1/algorithm/result.json) |
| DREAM / Codex 原生 | 无法完整判定：没有所需历史输出及同语义的混合前投影状态 | 115 | 3/3 | [结果](/Users/zanehuang/work/OptiRepro/reports/cpu30/analysis-2026-09-06/evidence/OptiRepro_cpu_2/agent_reproduction/runs/2212.02387/Codex原生-完整复现-Goal/第003次运行/judge/evaluations/paper-only-20260914T163221Z-1/algorithm/result.json) |
| DREAM / ReasFlow | 无法完整判定：没有所需历史输出 | 132 | 3/3 | [结果](/Users/zanehuang/work/OptiRepro/reports/cpu30/analysis-2026-09-06/evidence/OptiRepro_cpu_2/agent_reproduction/runs/2212.02387/ReasFlow实验Agent-完整复现-Goal/第003次运行/judge/evaluations/paper-only-20260914T163221Z-1/algorithm/result.json) |

这里的数值差异数是逐个标量比较的失败数，包含下游连锁影响，不是同等数量的独立算法缺陷。接口不足时保存部分数值证据，但不给完整实验通过或配置排名结论。

三次复测不只是状态相同：每个目标的实际观察 JSON、逐值比较 JSON 的标准化哈希也一致。12次 workspace 内容检查全部未变化。此结果验证固定标准下的执行重复性，不代表模型每次重新设计实验都同样稳定，也不代表已覆盖 CPU30 全部30篇。

## 已复核的有效性证据

- RSA Codex：第一个小实验中，原始目标函数回调和初态正确对应。代码将本地梯度额外除以总worker数3，使第一个worker首坐标为0.8083333，论文实验预期为0.275；主节点使用更新后的worker消息，首步master首坐标为0.625，预期为0.875。适配器没有抵消这两个行为。
- RSA ReasFlow：接口固定使用 alpha0/sqrt(step+1)，从第二步起不能表达冻结实验的步长表。只运行合法前缀，明确报告无法完整判断，未修改步长规则。
- DREAM：两库最早差异在尚未消费随机输入的step 0 tracker s，初始z/g均一致。给定W下原FastMix系数为0.25，论文标准为0.625，首个s值分别为3.125与3.0875。这排除了随机样本错位作为最早原因。
- 两个DREAM库都没有返回实验要求的历史输出候选和随机选取结果，不能由适配器从已有轨迹补造它们。原生库还不存在同语义的“混合前投影后”状态，这些均作为接口不足记录。

独立复核见 INDEPENDENT_EVIDENCE_REVIEW.md。首次DREAM适配器把一个混合后值标成混合前观察，已纠正并重跑；原始批次保留但不作为最终统计依据。

## 工程验证

59项聚焦测试通过。包括：论文阶段没有仓库信息/工具；公开输入不含答案；真实执行与原函数调用记录；正确轨迹通过；中间状态错误但最终值碰巧正确仍失败；自报pass不能替代实际数值；NaN/形状/重复/缺失拒绝；接口不足不误报通过；冻结契约损坏仍能输出失败报告；workspace防写和异常时权限恢复；相同源码安装副本的调用识别；评测目录不覆盖及运行目录独立。

测试输出位于 validation/unit-tests.txt。检查范围为新增执行层、标准比较层和已有静态归档路径；未重新调用静态rubric模型完成全量评分。

## 仍未验证通过的部分

额外测试了直接API自动出题。服务商简单请求可用，但两次 gpt-5.6-sol 原论文生成分别遭遇503 CPU overloaded与超时，gpt-4.1-mini尝试连接失败。没有生成可审阅的API契约，因此不能宣称“API自动出题—自动适配—执行”已全程稳定通过。

本次已实际完成的是：派真实独立Agent阅读原论文并推演，派独立Agent适配已有代码，再由新pipeline完成环境配置、原代码执行和逐值比较。API分支的会话隔离与顺序有单元测试，外部服务的完整成功路径仍需在可用服务下继续验收。

此外，论文推导本身可能出错，文件哈希仅绑定内容，不自动证明数学正确；适配器需要审查是否真的收集了正确位置的状态，函数调用记录不是对恶意适配器的安全保证。

## 使用入口

从原论文准备新标准：

```bash
python3 repo_judge/prepare_algorithm_judge.py --paper /path/paper.pdf --paper-id <id> --model <model> --output /path/new-standard
```

使用已独立准备的标准：

```bash
python3 repo_judge/run_execution_judge.py --repo /path/run/workspace --paper /path/paper.pdf --contract /path/contract.json --run-root /path/run --spec /path/adapter-settings.json
```

`--spec`可提供已审查的适配脚本和有来源说明的安装动作；省略时尝试自动生成适配及配置环境。运行模型需要JUDGE_API_KEY/JUDGE_BASE_URL或对应OPENAI环境变量。重测历史样本使用 validation/run_benchmark.py，可用 --targets 选择需要重测的目标。

本次没有发布新的全局不可变Judge版本，也没有切换CPU30正式批量调度入口。当前可以继续用新入口验证样本，尚不能据此承诺一万篇代码库的验收可靠性。
