# Judge 证据诊断与适用性检查改进

2026-09-15：已完成实现及相关测试。保留原有验收条件、比较容差、结果状态和 `optirepro.algorithm_assessment.v1`；本次新增诊断，不把缺项或小误差自动放行。

## 行为变化

- `algorithm_pipeline.py` 将最终执行 `reason_code` 与 `blocked_cases` 传入 `assess`。即使某个 case 的状态说明不合法，报告仍保留其他 blocked 说明及已比较数值，格式错误继续阻止验收。
- `assessment.evidence_summary` 同时呈现执行原因、实验适用性说明、实际观测覆盖、数值比较和审核/文件完整性。类别可并存，例如“接口自报受限、实验不完整、部分可比较数值不同”。
- 新诊断将缺少 case/观测/数组元素与格式错误分列；数组长度不符仍明确属于格式错误，不能被接口受限说明掩盖。旧 `protocol_errors` 与 `hold_reasons` 保留原含义，缺项依然阻止验收。
- `reported_limits` 明确来自 adapter 自报。原因文字不会触发“算法错误”结论，也不会覆盖数值差异。环境失败、无输出、超时、审核缺失和文件完整性失败有独立诊断。
- 修改 adapter 生成与独立审查提示，要求逐个实验核对算法变体、参数、初始化、随机值、dtype 和内部求解条件。不同条件下的原代码轨迹只能放入 `diagnostics`；只有语义可比较的实际观测进入 `observations`。允许逐 case 声明 `blocked/reason/missing_observations`，保留可比部分和其他实验，避免一项缺失使全部证据丢失。

生产文件：

- `repo_judge/src/judge/algorithm_assessment.py`
- `repo_judge/src/judge/algorithm_pipeline.py`
- `repo_judge/src/judge/review_records.py`（仅修改 `ADAPTER_REVIEW_PROMPT` 常量）

## 验证

工作目录 `repo_judge`，执行：

```sh
PYTHONPATH=. /tmp/optirepro-paper-judge-20260915/bin/python -m pytest -q tests/test_paper_contract.py tests/test_review_records.py tests/test_algorithm_pipeline.py
```

结果：**104 passed in 44.64s**。

新增或扩展的行为检查包括：接口限制仍保留部分数值差异；缺项不混成格式错误；部分数组既缺项又形状错误时不得隐藏后者；非法状态说明不能掩盖差异；环境失败不输出算法正确性结论；完整性失败与原始差异并存；完整匹配且审查通过才属于测试范围内通过。既有小误差不放宽容差、独立审查、原始函数调用和文件完整性测试继续通过。

范围限制：这些测试验证程序行为和提示传递，不证明外部 API 能稳定生成适用的实验或 adapter。尚未测试外部 API 生成一致性。真实论文的本轮回放与新实验由总报告单独记录，本文件不将其提前计为完成。
