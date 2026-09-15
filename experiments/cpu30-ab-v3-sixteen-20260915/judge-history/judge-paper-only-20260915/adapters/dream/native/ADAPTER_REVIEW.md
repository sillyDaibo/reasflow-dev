# DREAM 原生实现：外部算法内核适配审查

## 范围与独立性

本 adapter 仅阅读公开输入文件 `public_cases.json` 和目标 workspace 的算法、数据类型、目标函数与混合模块。没有读取契约预期、答案推导脚本、论文审查、仓库测试或参考输出；不比较数值答案，不作通过判定。

`adapter.py` 完全自包含。运行时只通过 `OPTIREPRO_WORKSPACE` 定位算法库，通过 `OPTIREPRO_CASES` 读取公开输入。它不写 workspace；输出一行 `OPTIREPRO_OBSERVATIONS=...`，缺失项在 stderr 明确说明。环境依赖 NumPy。

这是带给定目标函数和可行域的**算法内核测试**，不是原 logistic-regression 任务的整库端到端测试。原库没有直接暴露这些输入，因此通过明确的输入边界适配执行原始算法。

## 真正执行的代码

入口为 `dream_repro.algorithms.run_algorithm('DREAM', dataset, config)`。原 `_gradients`、`fast_mix`、`consensus` 和 DREAM 分支完整运行，包括全部 T 步、梯度估计、随机门控和跟踪器更新。`bindings.json` 列出真实算法调用。

没有替换 run_algorithm、梯度估计/跟踪更新、FastMix、混合函数或记录函数；没有重写其循环、公式、分支或历史状态保存逻辑。

## 输入边界

- 构造原 `Dataset` 数据类型，以连续分区的全局样本编号表达公开输入中的 agent/component；特征仅提供数据形状，synthetic objective 不使用虚构 logistic 数据。
- 原 `_initial_state` 返回时，trace 只将其 x/y 输入缓冲区调整为 `(agents, 1)` 并填入公开 `initial_z`。不赋值 g、s、旧状态或更新结果。
- 替换算法模块导入的 `local_gradient` 边界，按公开二次函数及原算法实际请求的样本计算平均梯度。回调不执行门控、q 缩放、旧梯度缓存或跟踪器更新。
- 替换算法模块导入的 `project_simplex_rows` 边界为给定 `y_interval` 的 clip，或无约束时 identity；保持原投影调用位置，即本实现的混合之后。未改 objective 模块里供原评估指标使用的 simplex 投影。
- 替换 RNG 工厂只提供给定 Bernoulli 与样本输入。仅响应原代码实际调用；原生实现只请求 node 0 的递归门控时，不替它补充 node 1 门控或估计器更新。
- 参数映射 `lr_x=gamma*eta`、`lr_y=eta`、`initial_mix=K0`、`small_mix=K`、`large_mix=K_prime`，以及 p、q、b、b_prime、T。原生代码将 large_mix 同时用于刷新分支状态和跟踪器，adapter 保留该行为，不补偿。
- 公开 W 可由原两节点 ring 接口表达，设置 kappa=W[0,0]，并在每次原 FastMix 调用验证实际生成矩阵与 W 一致。没有替换矩阵生成函数。

以上边界替换均在 finally 恢复；固定随机输入不意味着测试了随机分布质量。

## 观察来源

`sys.settrace` 在原 `_record` 调用时读取真实调用者 locals，得到 z=[x,y]、g、s；mean_z 只对真实 z 做观察性均值。在原 FastMix call 事件复制真实 values 入参，第三次调用即 tracker_input。

`pre_projection` 对应本轮混合和投影之前的真实下降/上升提议值，直接拼接原状态更新两次 FastMix 调用的 values 入参。原生实现只在混合之后投影，从未形成 schema 所指的混合前 `projected` 状态，因此每一步 `projected` 均省略；不把混合后投影结果冒充该状态，也不倒算构造。所有观察数组复制后保存，不反馈算法。

原代码返回指标 history，没有构造输出候选 x 历史集合，也没有根据历史随机索引返回 x。因此 `output_candidates` 与 `x_out` 均省略。每个 case 显式输出 `status="blocked"`、`reason` 与 `missing_observations`，保留其余真实观察，表示完整 case 的接口/状态覆盖不足，应由 pipeline 判为 INCONCLUSIVE。adapter 不从轨迹补造缺失步骤，不能据其余观察声称完整 case 通过。

## 验证

已使用 `/tmp/optirepro-cpu30-live-rsa/runtime/env/bin/python` 完整运行公开两 case，进程 exit 0。修正观察语义后重新 smoke，step 覆盖分别 0..3 与 0..2；输出分别 21 与 15 项观察，均为 blocked。各缺 output_candidates/x_out，以及每个迭代的混合前 projected。记录在同目录 smoke_observations.log 与 smoke_stderr.log。该检查仅验证实际执行及输出形状，不包含预期数值比较。
