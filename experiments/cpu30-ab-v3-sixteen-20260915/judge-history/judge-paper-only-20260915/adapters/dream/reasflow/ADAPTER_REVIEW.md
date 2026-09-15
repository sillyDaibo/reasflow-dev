# DREAM ReasFlow 实现：外部算法内核适配审查

## 范围与独立性

本 adapter 仅阅读公开输入文件 `public_cases.json` 和目标 workspace 的算法、数据类型、目标函数与混合模块。没有读取契约预期、答案推导脚本、论文审查、仓库测试或参考输出；不比较数值答案，不作通过判定。

`adapter.py` 完全自包含，通过 `OPTIREPRO_WORKSPACE` 定位算法，通过 `OPTIREPRO_CASES` 读取公开输入。它不写 workspace；输出一行 `OPTIREPRO_OBSERVATIONS=...`，缺失项在 stderr 明确说明。环境依赖 NumPy 和 scikit-learn：后者由原 `src/dream_reproduction/data.py` 顶层 `from sklearn.datasets import load_svmlight_file` 引入，即使 synthetic Dataset 不调用文件加载器仍须安装。

这是带给定目标函数和可行域的**算法内核测试**，不是原 logistic-regression 任务的整库端到端测试。原库没有直接暴露这些输入，因此通过明确的输入边界适配执行原始算法。

## 真正执行的代码

入口为 `dream_reproduction.algorithms.run_algorithm(dataset, 'DREAM', iterations=T, seed=0, config=config)`，它通过原 runner 映射进入 `_run_dream`。原 `_compute_gradients`、FastMix 和完整 DREAM T 步照常执行。`bindings.json` 列出真实算法调用。

没有替换 run_algorithm、_run_dream、梯度估计/跟踪更新、FastMix 或记录函数；没有重写其循环、公式、分支、混合动量状态或历史状态保存逻辑。

## 输入边界

- 构造原 `Dataset` 与连续分区，以样本全局编号表达公开 agent/component。synthetic objective 不使用占位特征与标签。
- 原 `_fresh_state` 返回时，trace 只将原 x/y 初始输入缓冲区调整为 `(agents,1)` 并填入公开 `initial_z`。不赋值 g、s、旧状态或更新结果。
- 替换算法模块导入的 `local_gradients` 边界，按公开二次函数和原算法实际请求的样本返回平均 gx/gy。回调不执行门控、q 缩放、估计器递推或跟踪器更新。
- 替换算法模块导入的 `project_simplex` 边界为给定 `y_interval` 的 clip，或无约束 identity；保持原代码逐节点投影然后 FastMix 的顺序。未改 objective 模块里评估指标的 simplex 投影。
- RNG 工厂仅提供公开 refresh/active/sample 实现值，按真实调用消费，保留原代码节点门控。
- 参数同名映射 eta、gamma、prob=p、q、b、b0=b_prime、K0、K、K_prime、T；eval_every=1 暴露每一步记录。公开 W 用原两节点 ring 的 tau=W[0,0] 表达，并在每次原 FastMix 调用验证矩阵，不替换矩阵生成或 FastMix。

边界替换均在 finally 恢复。固定随机输入不意味着测试了随机分布质量。

## 观察来源

`sys.settrace` 在原 `_record` 调用读取 `_run_dream` 的 x/y/gx/gy/sx/sy，拼接 z/g/s，并从实际 z 计算观察性 mean_z。在原 FastMix call 事件复制真实 values：每步前两次是 x/y 状态混合，后两次是 tracker_input 的 x/y 部分。

`pre_projection` 的 x 列取原 x FastMix 实际输入；y 列取每节点投影实际输入。`projected` 的 x 保持该原输入，y 取实际投影输出。这里只组合原算法已有的坐标子操作值，不重新计算状态更新式。观察数组复制后保存，不反馈算法。

原代码返回 RunResult 的指标 history，没有构造输出候选 x 历史集合，也没有根据历史随机索引返回 x。因此 `output_candidates` 与 `x_out` 均省略。每个 case 显式输出 `status="blocked"`、`reason` 与 `missing_observations`，保留全部其余真实观察，表示完整 case 覆盖不足，应由 pipeline 判为 INCONCLUSIVE。adapter 不从轨迹补造缺失步骤，不能据其余观察声称完整 case 通过。

## 验证

首次 smoke 使用 `/tmp/optirepro-cpu30-live-rsa/runtime/env/bin/python`，在导入原 data.py 时因缺少 scikit-learn 失败；未产生算法观察。依赖齐全后的完整执行状态另行更新。本 adapter 不以原生库的执行替代 ReasFlow 实际执行。
