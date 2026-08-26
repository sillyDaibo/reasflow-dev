# ReasFlow Survey 的 Codex-first 重构：调查、诊断与实验设计

## 1. 问题

旧 ReasFlow 的 Survey agent 以 Codex 为底座，却在若干盲评任务上不如纯 Codex。
这不能直接解释为“工作流没有价值”，因为旧比较同时改变了 agent 编排、检索源、
上下文构造和写作自由度。本轮重构首先要恢复 Codex 的原生研究和写作能力，再单独
测量可靠性工具与 ReaScholar 的增益。

## 2. 已有研究说明了什么

目前没有找到专门评测 Codex CLI 原生撰写完整学术 Survey 的公开研究。下列结论来自
自动 Survey、Deep Research、长上下文研究和本地生成结果，应避免把它们误写成
“已有论文已经证明 Codex 如何”。

- [OpenAI 最新模型提示指南](https://developers.openai.com/api/docs/guides/latest-model)
  建议提供目标、边界和成功条件，但减少重复规则和逐步处方；官方内部 coding-agent
  经验也显示 leaner prompt 可以同时改善质量、token 和成本。
- [LitLLMs](https://arxiv.org/abs/2412.15249) 说明轻量 planning、检索和 attribution
  能改善较短的文献综述，但它不支持把完整长文拆成大量固定 worker 和冻结 handoff。
- [AutoSurvey](https://arxiv.org/abs/2406.10252) 明确承认并行分段生成会产生 transition
  和 consistency 问题，因此需要额外 refinement。
- [SurveyForge](https://arxiv.org/abs/2503.04629) 认为自动 Survey 与人工 Survey 的主要
  差距仍包括 outline quality 和 citation accuracy。
- [DeepSurvey](https://arxiv.org/abs/2605.29522) 将现有系统的根本缺陷归纳为摘要级浅
  分析、孤立处理论文、检索不精确和事后引用对齐；其改进集中在全文证据、跨论文关系、
  citation graph 和 claim-level attribution。
- [ReportBench](https://arxiv.org/abs/2508.15804) 发现商业 Deep Research agent 通常比
  单模型加搜索更全面可靠，但仍有 coverage、depth 和 factual consistency 空间。
- [BrowseComp-Plus](https://arxiv.org/abs/2508.06600) 说明必须拆开检索与 agent 能力，
  固定检索环境后才能做公平归因；更好的 retriever 可同时提高效果并减少搜索调用。
- [Lost in the Middle](https://arxiv.org/abs/2307.03172) 与
  [OP-RAG](https://arxiv.org/abs/2409.01666) 表明长上下文利用并不稳健，增加 retrieved
  chunks 存在倒 U 型收益，不能把“给 writer 更多论文”视为单调改进。

## 3. 本地结果和根因

旧 15k 八任务比较中，ReaScholar+S2 相对相同 ReasFlow 写作流程的 S2-only：

- blind overall 为 6 胜 2 负；
- lineage 为 7 胜 1 负；
- comparative synthesis 为 7 胜 1 负；
- gap grounding 为 3 胜、4 负、1 平；
- future work 为 4 胜、4 负。

这说明 ReaScholar 已经能改善结构关系，但 open problems 到最终正文的传递仍不稳定。
它不是“完全无增益”，也没有证明整体稳定领先。

ReaScholar+S2 与纯 Codex 的三题盲评中：

- Error Feedback：ReaScholar 三位 reviewer 全面胜出；
- Quantized Communication：纯 Codex 在 taxonomy、pedagogy 和多数 gap/future 票上占优，
  ReaScholar 在 lineage 更强，但检索中出现 topic 弱对齐论文；
- Hierarchical Systems：纯 Codex 的统一 taxonomy、机制比较和教学路径明显更好，
  ReaScholar 文章的 Domain 分支更宽、更散。

旧实现对 Survey 施加了以下额外负担：

1. 顶层和三个 worker 共有约四万字符 developer instructions；
2. writer prompt 约 11--14 万字符，包含最多 140 篇压缩证据；
3. outline 在完整写作前被冻结，writer 不能根据后续发现重组文章；
4. writer 禁止继续检索，而纯 Codex 可以边写边核验；
5. 旧输出出现 42--44 个小节，造成覆盖广但每节过浅；
6. Domain prose 过早进入 outline，检索污染会成为文章结构锚点；
7. 多个 agent handoff 使 taxonomy、timeline、gap 和正文的因果主轴分离。

因此，旧结果不能解释为“纯 ReasFlow 本身的模型能力低于 Codex”。更准确的说法是：
ReasFlow 对同一个 Codex 增加了过强的策略约束、不同的工具权限和更嘈杂的证据上下文。

## 4. 新默认架构

新 Survey 只有一个内容 owner：Codex 自己负责研究问题、检索决策、动态 outline、完整
TeX、Related Works 和修订。ReasFlow 不替它规定思考步骤，只提供三层能力：

1. **检索层**：native Web 负责广泛发现，S2 负责可复现 metadata 与 citation/reference
   graph；返回小批 paper cards，而不是一次性注入完整 pool。
2. **ReaScholar 层**：提供 Domain/category、paper details、citation relations、limitations、
   open problems 和 later-work candidates；所有内容都是待核查 hypothesis。
3. **可靠性层**：canonical registry、DOI/Crossref 反查、BibTeX 生成、citation key、重复
   检查、TeX/PDF 编译和 publication gates。

ReaScholar 的优势应通过如下可观察链条进入文章：

```text
paper-stated limitation
        ↓
later-work / counterevidence search
        ↓
unresolved scope at cutoff
        ↓
testable future study
```

Category 也不能直接成为标题。Codex 应先判断它是否代表独立的 mechanism、assumption、
guarantee 或 deployment axis，并检查是否有代表论文。

## 5. 公平消融

三臂使用同一个 `prompt.txt`、同一个公共 task projection、同一个模型、reasoning effort、
截止日期和运行预算：

| Arm | native Web | S2 | deterministic reliability | ReaScholar |
|---|---:|---:|---:|---:|
| Pure Codex | 是 | 否 | 否 | 否 |
| ReasFlow Codex-first | 是 | 是 | 是 | 否 |
| ReasFlow + ReaScholar | 是 | 是 | 是 | 是 |

公共 prompt 只说明研究目标、10k--12k words、100+ relevant papers、45--55 Related Works、
TeX/PDF 和作者标签，不规定 citation command、章节数量、检索顺序或 ReaScholar 特征。
出版规范只存在于 ReasFlow skill 中，这正是框架希望提供的能力。

Pure Codex 与 ReasFlow Codex-first 测量薄框架是否保留原生能力并修复可靠性；
ReasFlow Codex-first 与 ReaScholar arm 才是 ReaScholar 的因果消融。

## 6. 评测解释

出版、引用可靠性与内容盲评分开报告，不将其任意合成一个总分。内容盲评保留 taxonomy、
lineage、comparative synthesis、pedagogy、gap grounding 和 future-work quality。

ReaScholar 的结构价值另外检查：

- category 是否由代表论文和可区分的 comparison axis 支持；
- timeline 是否具有 predecessor -> limitation -> successor 证据；
- open problem 是否有 originating paper、later-work 检查和明确的 unresolved scope。

这些检查对三臂使用相同标准。指标进入结论前必须能识别 wrong-paper substitution、topic
drift、duplicate identity、timeline scramble、counterevidence removal 和 fabricated future
work 等 mutation。负向结果必须定位到检索、Domain、metadata、evidence utilization、写作
组织或 evaluator，而不是通过调权或删任务处理。

## 7. 当前实现状态

- 旧状态已备份到远端分支 `backup/survey-15k-pre-codex-first-20260827`，commit
  `3bcd928db96771351607a7963cc5319dce407056`。
- 开发分支为 `refactor/codex-first-survey`。
- 三个旧 Survey worker 已从默认安装中删除。
- 新 registry 工具支持 merge、shortlist、inspect、ReaScholar structure filtering、DOI
  Crossref validation、BibTeX 和 research audit。
- 三臂 runner 拒绝 evaluator-only task 字段，并记录公共 prompt SHA。
- Error Feedback 的三臂 prepare-only smoke 已确认公共 prompt 与 task projection 一致。

本文件记录设计和诊断；最终实验结果应另写结果报告，不应把设计动机当成已经观察到的优势。
