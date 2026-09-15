# CPU30 RSA / Codex 外部适配审查

入口为自包含的 `adapter.py`；可单独复制运行，不依赖相邻文件。输入只来自环境变量 `OPTIREPRO_CASES` 指定的 public JSON；通过 `OPTIREPRO_WORKSPACE` 导入原 `rsa_repro.rsa`。没有读取契约预期、答案推导、论文审查或仓库测试。禁止写入 bytecode，原 workspace 文件不变。

## 算法绑定和注入边界

实际执行原 `rsa_step`，实际调用原 `norm_subgradient`，未替换它们或更新、求和、步长、归一化规则。给定初态通过原 `RSAState` 设置；给定步长通过原 `alpha` 参数逐轮传入，lambda 和 master 的单位二次正则通过原 `lam` / `weight_decay=1` 参数设置。

原实现 hardcoded `softmax_gradient` 被替换为测试输入的二次损失梯度 `theta - center`，这是目标函数边界注入。原实现紧接着执行的 `/ workers` 完整保留，未放大输入梯度抵消它。原实现还为 Byzantine worker 分配并更新内部 local；测试没有为其指定优化目标或初态，因此这些隐藏 local 初始化为零、目标梯度为零，其值不作为测试观察输出，且被指定 Byzantine 消息覆盖。

原攻击枚举不能表达 public 输入给出的逐坐标任意向量及逐轮变化。适配器需要外部 Byzantine 发送消息边界注入：仅 `attack_message` 返回 public 对应轮/发送者数组，不改变 RSA 接收后的使用方式。此处替换的是测试环境的恶意发送者，不是 RSA 更新/聚合函数；主代理已明确批准此测试输入边界，运行时仍保留原 RSA 更新/聚合。

## 观察来源

- `master` / `regular_workers`：原 `RSAState` 初态、每轮原函数返回状态。
- `worker_loss_gradients_before_update`：注入目标函数当次实际返回梯度；原函数仍自行除以 workers。
- worker penalty 和 Byzantine master subgradient：`sys.settrace` 捕获原 `norm_subgradient` 返回，不另行计算范数。
- master penalty sum：从原 `rsa_step` 的 `penalty` 局部变量读取。
- master regularizer gradient：只读原更新操作数 `weight_decay` 和旧 `state.master` 的乘积。原实现未给该项单独命名变量，适配器只生成观察值，不将此乘积反馈给算法。

原实现实际使用 `received = next_local.copy()` 后的消息计算 master penalty。适配器保留此时序；观察名称中的 before_update 指该函数实际执行 master 更新之前，未重新按其他时序计算。

## 范围

三个 public case 的 p 参数均有原生分支；Codex 的显式 alpha 接口可表达整个测试步长序列。这里只核对适配、数据形状和原函数确实运行，不读取或比较 expected 数值。

## Smoke 验证

2026-09-15 使用 bundled Python 3.12.14 / NumPy 2.3.5 运行，退出码 0，stderr 为空。三个 case 分别收集 23 / 16 / 16 个观察，完整覆盖 public observation_schema。仅核对观察键、唯一性和 shape，未读取或比较 expected。原算法文件运行前后 SHA-256 相同。详见 `smoke.stdout.txt`。
