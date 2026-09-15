# CPU30 RSA / ReasFlow 外部适配审查

入口为自包含的 `adapter.py`；可单独复制运行，不依赖相邻文件。仅读取 public JSON 与原算法源码，不读取契约预期、答案推导、论文审查或仓库测试。通过 `OPTIREPRO_WORKSPACE` 导入原 `rsa_reproduction.algorithms`，禁止写 bytecode，原 workspace 不变。

## 原生算法和状态边界

实际执行原 `run_training` 和原 `norm_subgradient`；不替换或复制 RSA 更新规则。训练器硬编码模型为 float32 的 `(10, feature_dim + 1)`，给定向量嵌入第一行，其他坐标保持零。通过 `sys.settrace` 在循环开始前一次性向原数组写入 public 初始 master/regular worker 值，保留原 dtype 与分配；观察只取嵌入坐标。零填充不会增加非零 norm 坐标。原分类评估照常执行，但其 accuracy/loss 不属于这些测试观察，也不影响更新。

原 hardcoded `softmax_gradient` 被替换为 public 指定的二次损失梯度，原 `/ workers` 完整保留。Byzantine 内部隐藏 local 从原零初态开始、目标梯度为零，随后消息由外部输入给定。只替换 `_attack_message` 的恶意发送者边界；正常发送者继续调用原 helper。原攻击枚举无法表达逐坐标任意给定消息，主代理已明确批准此测试输入边界，运行时仍保留原 RSA 更新/聚合。

## 无法表达完整测试步长

原实现仅接受 alpha0，并硬编码 `alpha = alpha0 / sqrt(step + 1)`。三个 public case 的第 2 轮均与该调度不符。适配器只执行给定 schedule 的共同有效前缀，即第 1 轮。它不会覆写 alpha、反复重启训练器、补偿 alpha0，或运行错误 schedule 后冒充正确输入。

输出保留 step 0 / step 1 的实际观察，同时每个 case 标记 `status=blocked`，`reason` 给出首个不匹配步长，后续观察故意缺失。完整 case 不能算验证通过；前缀结果仍可用于诊断实际原实现行为。

## 观察来源

目标函数当次返回值用于 loss gradient；原 norm 函数的 return trace 用于 penalty subgradient；原 `penalty` 局部变量用于聚合项；原 `theta` / `local` 数组用于状态。master regularizer 项只读原 `l2` 与保存的当轮旧 theta 乘积，不反馈算法。保持原消息源为更新后 local 的执行时序，不重算另一种时序的值。保留 float32 精度影响。

这里只检查入口执行、观察形状、前缀轮数和 blocked 报告；不读取或比较 expected 数值。

## Smoke 验证

2026-09-15 使用 bundled Python 3.12.14 / NumPy 2.3.5 运行，退出码 0，stderr 为空。三个 case 各收集 9 个观察，恰为 step 0 / 1；全部报告 blocked，第 2 轮及以后未运行。仅核对观察键、唯一性和 shape，未读取或比较 expected。原算法文件运行前后 SHA-256 相同。详见 `smoke.stdout.txt`。
