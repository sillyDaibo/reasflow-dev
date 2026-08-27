# ReasFlow 对 Pure Codex 负增强修复：两题 canary 结果

日期：2026-08-27  
性质：内部实验；开发题 canary，不是排行榜结果

## 1. 当前结论

旧 ReasFlow 在 Extragradient 上曾被 Pure Codex 的三位匿名 reviewer 一致判负。
删除强制 staged workflow、冻结 outline、worker handoff、大证据池和默认多-skill 注入后，
相同失败题的总体票逆转为 ReasFlow `2:1`。在独立的 Error Feedback 题上，进一步精简为
cited-only postflight 后，ReasFlow 获得 `3:0` 总体票。

两题合计：

- 任务级总体胜负：ReasFlow `2/2` 胜；
- reviewer 总体票：ReasFlow `5`、Pure Codex `1`、平票 `0`；
- 54 个维度票：ReasFlow `32`、Pure Codex `13`、平票 `9`；
- 两题 core mechanical 均完全打平；
- 两边 publication gate、canonical duplicate、BibTeX consistency 均通过。

因此，现有证据已经支持“系统性的负增强已被止住，Minimal ReasFlow 在两个开发题上优于
Pure Codex”。但统计单位是任务而不是 reviewer；当前只有两个任务，不能宣称稳定显著优势，
也不能把 `5:1` reviewer 票当作六个独立任务做显著性检验。

## 2. 根因与修复

旧实现额外向同一底座模型注入约 2,700 词强制流程，并要求固定 outline、分阶段检索、
大候选池、worker handoff 和模板化 gap/future 检查。旧 Extragradient case 中，这导致：

- 用 2002/2003 年后续分析替代 Korpelevich/Rockafellar 原始工作；
- Tseng、Malitsky 等方法的 claim--citation 错配；
- 章节碎片化、机械重复和原生跨方法综合能力下降；
- 工具生成 taxonomy 过早成为文章结构，而不是待验证信息。

当前 ReasFlow 只保留三个窄增强：

1. 对正文实际选中或引用的论文做 canonical identity 与 metadata 检查；
2. 仅在具体 claim 无法确认时补充原文、citation neighbor 或 paper detail；
3. 在正文完成后做 TeX、BibTeX、canonical duplicate、citation key 和 PDF postflight。

Codex 自己决定研究顺序、taxonomy、timeline、文章主线、prose 和修订。默认
`survey.toml` 只暴露一个 Codex-first skill；ReaScholar、S2 helper、packaging 和
workspace cartography 不再自动注入。ReaScholar 只有在任务或运行 profile 明确请求时
才打开相应工具。

本轮还修复了两类可靠性缺陷：

- publication builder 原来只查重复 BibTeX key，现同时按 DOI、arXiv ID 和 normalized
  title 检测不同 key 指向同一 canonical paper；
- named-origin linter 现可区分联合姓氏与方法名，不再把 `Mirror-Prox`、`FedAvg`、
  `SignSGD`、`PowerSGD` 当成人名。

## 3. 公平协议

两臂使用完全相同的：

- 公共 prompt，SHA-256 为
  `8df3fa2b0c13a1945abf2019acf23fa65fd79f515394e7c9beb7a1d732bc24e1`；
- `gpt-5.6-terra`、`high` reasoning effort；
- topic、cutoff、10,000+ words、100+ relevant papers、45--55 Related Works；
- TeX/PDF、canonical dedup 和 deterministic publication gate；
- 静态 evaluator 和 9 维匿名 pairwise rubric。

公共 prompt 不要求某种 citation command、不泄露 evaluator key references，也不规定
taxonomy、timeline、gap/future 的答案或 ReasFlow 工具使用方式。

9 个盲评维度为 taxonomy、research lineage、timeline、comparative synthesis、paper-detail
depth、pedagogical clarity、gap grounding、counterevidence handling 和 future-work quality。

## 4. 静态与出版结果

| 任务 | Arm | 主文词数 | 主文引用 | Related Works | Core /21 | Diagnostic /19 | `/40` |
|---|---|---:|---:|---:|---:|---:|---:|
| Extragradient | Pure Codex | 10,732 | 120 | 51 | 21.000 | 17.092 | 38.092 |
| Extragradient | Minimal ReasFlow | 10,245 | 102 | 50 | 21.000 | 16.149 | 37.149 |
| Error Feedback | Pure Codex | 10,804 | 102 | 55 | 17.667 | 16.577 | 34.244 |
| Error Feedback | Minimal ReasFlow | 10,643 | 101 | 48 | 17.667 | 16.209 | 33.876 |

两题 core 分完全相同。ReasFlow 的 `/40` 略低，全部来自 diagnostic-only 的引用密度、
总参考条目和长度接近 target 的程度。这些计数不能证明组织、综合或事实质量，并会奖励
重复 citation occurrence，因此不应用它们否定盲评内容优势，也不应为了让总分反转而修改
文章或权重。后续正式报告应把 `/21` core 与 `/19` diagnostic 分开，不把 `/40` 当作唯一
排序。

Extragradient 首次生成暴露两组 canonical duplicate：`malitsky2018` / 
`malitsky2020goldstein` 和 `beznosikov2021` / `beznosikov2022`。严格 evaluator 正确拒绝该稿；
修复是合并 canonical identity 并升级 builder，而不是放宽 evaluator。修复后两组均为 0，
重新编译通过。

## 5. 匿名 pairwise 结果

### 5.1 Extragradient

总体票：ReasFlow `2:1` Pure Codex。平均维度 pair agreement 为 `0.6296`，总体 agreement
为 `0.3333`，说明总体方向已逆转，但 reviewer 对部分维度仍有分歧。

| 维度 | Pure | ReasFlow | Tie | 多数结论 |
|---|---:|---:|---:|---|
| Taxonomy | 3 | 0 | 0 | Pure |
| Lineage | 0 | 2 | 1 | ReasFlow |
| Timeline | 2 | 1 | 0 | Pure |
| Comparative synthesis | 2 | 1 | 0 | Pure |
| Paper detail | 0 | 3 | 0 | ReasFlow |
| Pedagogy | 0 | 3 | 0 | ReasFlow |
| Gap | 1 | 2 | 0 | ReasFlow |
| Counterevidence | 0 | 3 | 0 | ReasFlow |
| Future work | 0 | 2 | 1 | ReasFlow |

Pure Codex 的主要缺陷不是没有知识，而是局部 citation--claim 错配：reviewer 具体指出
AdaGrad reference 被用于 bilinear stability 论述、Frank--Wolfe reference 被放入 dual
extrapolation 讨论。Minimal ReasFlow 对原始工作归因、paper-specific mechanism、适用条件
和 evidence boundary 更可靠。

### 5.2 Error Feedback

总体票：ReasFlow `3:0` Pure Codex，总体 agreement 为 `1.0`。平均维度 agreement 为
`0.5555`；低维度 agreement 主要来自大量合理 tie，而不是总体排序冲突。

| 维度 | Pure | ReasFlow | Tie | 多数结论 |
|---|---:|---:|---:|---|
| Taxonomy | 0 | 1 | 2 | 无实质差异 |
| Lineage | 0 | 2 | 1 | ReasFlow |
| Timeline | 3 | 0 | 0 | Pure |
| Comparative synthesis | 2 | 0 | 1 | Pure |
| Paper detail | 0 | 2 | 1 | ReasFlow |
| Pedagogy | 0 | 2 | 1 | ReasFlow |
| Gap | 0 | 2 | 1 | ReasFlow |
| Counterevidence | 0 | 3 | 0 | ReasFlow |
| Future work | 0 | 3 | 0 | ReasFlow |

最有解释力的 case 是 private/clipping error feedback。ReasFlow 找到并正确限定 2024 年
`Differentially private SGD without clipping bias: An error-feedback approach`，把它作为部分
解决和 counterevidence：它说明 error feedback 可以缓解 clipping-associated optimization
bias，但不能取消 DP noise、敏感度控制或完整 transcript accounting。Pure Codex 没有纳入
这一直接相关工作，却更广泛地暗示 joint private error-feedback literature 很薄。三位 reviewer
因此一致把 counterevidence 和 future work 判给 ReasFlow。

## 6. 对 ReasFlow 设计的约束

两题给出一致边界：

- 应由 Codex 原生负责：taxonomy、phase-level timeline、跨方法 comparative synthesis；
- ReasFlow 应增强：paper identity、original-source attribution、paper detail、scope/assumption
  边界、later work、counterevidence、gap 到 testable future work 的证据链；
- 不应恢复：固定 outline、taxonomy template、完整候选池注入、worker 分段写作、冻结 handoff、
  统一 gap/future checklist；
- ReaScholar 后续只能作为可选择 evidence layer，不能把 Domain/category/timeline 直接变成
  标题或结论。

下一准入门槛不是继续增加 prompt，而是在至少 4 个冻结留出题复验：任务级
`ReasFlow >= Codex` no-regression，并保持上述同 prompt、同模型、同 publication gate。
只有通过后才恢复 ReaScholar 增量实验。

## 7. 复现路径

- ReasFlow 代码分支：`refactor/codex-first-survey`
- 最新修复提交：`adfb360`
- Extragradient 运行根目录：
  `/home/iceysakura/lab/paper_gen/reasflow-workspaces/runs/2026-08-27-reasflow-minimal-parity-v1`
- Error Feedback 运行根目录：
  `/home/iceysakura/lab/paper_gen/reasflow-workspaces/runs/2026-08-27-reasflow-minimal-parity-v2`
- Extragradient pairwise：
  `eval/blind-extragradient-reasflow-vs-pure-v1/pairwise.json`
- Error Feedback pairwise：
  `eval/blind-error-feedback-reasflow-vs-pure-v1/pairwise.json`

每个运行目录同时保留 frozen public task、prompt、manifest、源代码 snapshot hash、TeX、PDF、
publication validation、匿名 packet、私有 arm mapping、三份 reviewer judgment 和聚合结果。
