# 从 Codex 的 Survey 能力边界到 Minimal ReasFlow

日期：2026-08-27
实验性质：内部开发题 canary；不是排行榜结果

## 1. 结论先行

这轮重构的出发点不是假定 Codex 不会写 Survey，而是承认它已经是很强的长文研究与写作
baseline。旧 ReasFlow 的主要问题，恰恰是用固定工作流、模板和大证据池覆盖了 Codex 本来
较强的研究规划、taxonomy、timeline 和 comparative synthesis 能力。

重构后，ReasFlow 不再替 Codex 规划文章，只针对 Codex 的几个局部、可测、可机械核验的
缺陷提供薄增强。旧失败题 Extragradient 从 Pure Codex `3:0` 胜旧 ReasFlow，逆转为
Minimal ReasFlow `2:1` 胜 Pure Codex；独立 Error Feedback 题上，Minimal ReasFlow 又以
`3:0` 获胜。两题合计 ReasFlow 获得 `5/6` 总体 reviewer 票，任务级 `2/2` 胜，同时两题
core mechanical 都与 Pure Codex 完全打平。

当前证据支持：

> 在这两个开发题上，删除负增强后，Minimal ReasFlow 已经做到
> `ReasFlow > Pure Codex`；但只有两个任务，尚不能声称统计显著的普遍排序。

## 2. Codex 原生能力：强项与缺陷

### 2.1 不应被 ReasFlow 干预的强项

两题匿名评审一致表明，Pure Codex 的强项主要在宏观组织和跨方法综合：

- 能根据 topic 自行找到统一的 conceptual spine，而不是按论文逐篇罗列；
- 能提出有用的 taxonomy 轴，并把机制、假设、保证和 deployment 联系起来；
- phase-level timeline 清楚，能解释一个阶段为什么转向下一个阶段；
- comparative synthesis 强，尤其擅长把算法放到相同 oracle、projection/prox、通信、隐私
  或系统预算下比较；
- 能在写作过程中继续搜索、核验并动态调整文章结构。

两题累计匿名票中，Pure Codex 在 timeline 为 `5:1`，comparative synthesis 为 `4:1:1 tie`；
Extragradient 的 taxonomy 为 `3:0`。这些能力应继续由 Codex 原生负责，ReasFlow 不应通过
固定 taxonomy 或 timeline 模板与它竞争。

### 2.2 ReasFlow 应针对的局部缺陷

#### 缺陷 A：局部 claim--citation 对齐不稳定

Codex 可以写出整体正确的故事，但个别 citation 可能只与段落主题相关，并不支持紧邻的
具体机制或历史归因。Extragradient 的匿名 reviewer 发现：

- AdaGrad reference 被用于 bilinear stability 论述；
- Frank--Wolfe reference 被放入 dual extrapolation 讨论；
- 个别 paper title、作者或年代与邻接的方法性论断没有完全对齐。

这类错误不会被“引用键存在”“引用数量足够”检测出来，需要 original-source、paper identity
和窄 claim-boundary 检查。

#### 缺陷 B：原始工作可能被后续分析替代

旧 Extragradient case 曾用 2002/2003 年后续 convergence analysis 支持
Korpelevich/Rockafellar 的原始贡献。搜索结果排在前面并不意味着它就是 first/original
source。对普通相关性检索而言这不严重，但对 Survey 的 method lineage 是实质性错误。

#### 缺陷 C：canonical identity 与 bibliography metadata 容易污染

长文同时使用 arXiv、会议版、期刊版和不同搜索源时，Codex 容易出现：

- 不同 BibTeX key 指向同一论文；
- preprint 与 published version 同时被当成两篇；
- DOI、title、venue、year 之间不一致；
- BibTeX key 不重复，但 normalized title 或 DOI 实际重复。

本轮首次 Extragradient 稿就真实出现两组：

- `malitsky2018` / `malitsky2020goldstein`；
- `beznosikov2021` / `beznosikov2022`。

严格 evaluator 正确拒绝了该稿。问题通过合并 canonical identity 和升级 builder 修复，而
不是放宽 evaluator。

#### 缺陷 D：later work 与 counterevidence 搜索不总是充分

Codex 能提出合理 gap，但可能没有找到直接相关的 later work，因而把已经部分解决的问题
描述得过宽。Error Feedback 中，Pure Codex 没有纳入 2024 年
`Differentially private SGD without clipping bias: An error-feedback approach`，从而更广泛地
暗示 private error-feedback 文献仍很薄。

ReasFlow 稿找到这项工作，并准确限定：它是 clipping-associated optimization bias 的部分
解决，不代表可以取消 DP noise、敏感度控制或完整 transcript accounting。三位 reviewer
因此一致把 counterevidence 和 future-work quality 判给 ReasFlow。

#### 缺陷 E：paper detail 与 scope boundary 偶尔停留在摘要级故事

Codex 原生文章能讲清大方向，但未必始终写出某项工作的具体 retained state、injection
location、assumption、guarantee、oracle model 和适用边界。缺少这些细节时，taxonomy 和
future work 看似合理，却难以判断是否真正来自论文证据。

#### 缺陷 F：出版与交付可靠性不是内容模型的稳定强项

即使正文好，仍可能出现重复 canonical paper、BibTeX metadata 缺失、表格溢出、citation
key 未定义、公式或 PDF 编译问题。这些适合确定性工具解决，不值得用更多写作 prompt
占用模型注意力。

## 3. Minimal ReasFlow 最终只保留什么

Minimal ReasFlow 把内容决策权完全还给 Codex，只保留下列窄增强。

### 3.1 Cited-only canonical identity 与 metadata postflight

Codex 先按自己的研究和写作顺序选择论文、建立叙事、完成正文。ReasFlow 不在写作前
构造大候选池，也不要求先生成完整 BibTeX；只对正文实际选择或引用的 paper 做：

- DOI、arXiv ID、normalized title canonicalization；
- preprint / conference / journal identity 合并；
- title、author、year、venue、DOI 的保守核验；
- canonical duplicate 与 citation-key gate。

这样既修复 bibliography，又不让 metadata 检索顺序决定文章 taxonomy。

### 3.2 针对具体不确定点的 evidence helper

Native Web 仍是默认 discovery。只有当 Codex 对一个具体问题不确定时，才使用 S2、
ReaScholar 或 registry helper，例如：

- 这篇是否真是 original paper；
- 两个结果是否是同一 canonical paper；
- 某项 method 的具体 assumption 或 guarantee；
- 某篇 paper 的 references/citations 中是否存在 successor 或 counterevidence；
- 某个 gap 在 cutoff 前是否已经部分解决。

工具返回的是待核验 evidence，不是 outline、标题或标准答案。

### 3.3 窄 named-origin attribution audit

凡句子明确声称某人 introduced、proposed、established 或某人的方法是 foundation，attached
citation 必须包含对应作者并代表原始工作；否则应改成 qualified secondary account。

该检查只处理历史归因，不规定 timeline 或研究叙事。审计器同时排除
`Mirror-Prox`、`FedAvg`、`SignSGD`、`PowerSGD` 等方法名假阳性，并正确支持
`Eckstein--Bertsekas` 等联合归因。

### 3.4 Deterministic publication postflight

正文完成后统一做：

- TeX 编译与 PDF 生成；
- citation-key resolution；
- DOI/arXiv/title canonical duplicate；
- BibTeX 最低 metadata；
- 重复段落、篇幅、引用数量、Related Works 范围；
- 表格、公式、字体和页面布局检查。

这些检查发现问题时只做针对性修复，不重写 taxonomy、timeline、gap 或文章主线。

### 3.5 默认上下文只有一个 Codex-first skill

默认 `survey.toml` 不再同时自动加载 retrieval、ReaScholar、packaging 和 workspace
cartography skill。它只暴露一个很短的 Codex-first contract。其他工具文件仍保留，但只有
任务或运行 profile 明确请求时才打开。

## 4. 大幅删除了什么

| 旧设计 | 为什么构成负增强 | 当前处理 |
|---|---|---|
| 顶层 agent + 多个 outline/section/related-work worker | 内容 ownership 分裂，handoff 丢失文章主线 | 删除；Codex 单一 owner |
| 固定 staged workflow | 用框架步骤替代 Codex 原生规划 | 删除 |
| 写作前冻结 outline | 后续发现无法改变 taxonomy 和主线 | 删除；动态组织 |
| 一次注入 100+ paper cards / 大 evidence pool | 长上下文噪声，metadata 顺序锚定结构 | 删除；cited-only postflight |
| 工具生成 taxonomy 直接变成标题 | topic drift 会进入全文骨架 | 删除；只作 hypothesis |
| 强制 timeline/gap/future 模板 | 抑制 Codex 原生比较和论证方式 | 删除 |
| writer 禁止继续搜索 | 无法边写边核验和修正 | 删除；native Web 默认可用 |
| 多套重复 developer instructions | 占用注意力，重复约束 | 从约 2,700 额外词缩到约 200 词核心说明 |
| 默认自动加载多个 survey skills | skill trigger 重新引入旧阶段 | 删除；默认只留一个 core skill |
| 只按 BibTeX key 去重 | 不同 key 的同一论文可逃过检查 | 改为 DOI/arXiv/title canonical gate |
| 大而泛化的 claim audit | 容易假阳性并反向污染正文 | 收窄到 named-origin；内容交给盲评/证据评测 |

## 5. 公平实验设置

Pure Codex 和 Minimal ReasFlow 使用相同：

- 公共 prompt，SHA-256：
  `8df3fa2b0c13a1945abf2019acf23fa65fd79f515394e7c9beb7a1d732bc24e1`；
- 模型：`gpt-5.6-terra`；
- reasoning effort：`high`；
- topic、cutoff 和运行预算；
- Survey 10,000+ words、100+ relevant papers；
- Related Works 1,200--2,200 words、45--55 papers；
- TeX/PDF 和 canonical duplicate hard gate；
- 静态 evaluator 与 9 维匿名 pairwise rubric。

公共 prompt 不规定 citation command、taxonomy、timeline、gap/future 答案或 ReasFlow 工具
使用方式。ReasFlow 的优势必须来自它自己的薄可靠性设计，而不是给 Codex baseline 一个
更差的任务。

## 6. 最终得分对比

### 6.1 出版与静态评测

| 任务 | Arm | Survey words | Survey papers | Related papers | Core /21 | Diagnostic /19 | `/40` |
|---|---|---:|---:|---:|---:|---:|---:|
| Extragradient | Pure Codex | 10,732 | 120 | 51 | 21.000 | 17.092 | 38.092 |
| Extragradient | Minimal ReasFlow | 10,245 | 102 | 50 | 21.000 | 16.149 | 37.149 |
| Error Feedback | Pure Codex | 10,804 | 102 | 55 | 17.667 | 16.577 | 34.244 |
| Error Feedback | Minimal ReasFlow | 10,643 | 101 | 48 | 17.667 | 16.209 | 33.876 |

两题 core mechanical 完全打平，双方 publication、canonical duplicate、citation validity 和
BibTeX consistency 均通过。ReasFlow 的 `/40` 略低，差值全部来自 diagnostic-only 的引用
occurrence、总 bibliography 条目和离 target word count 的距离。

这些计数不等价于文章质量，且可能奖励重复引用或冗长，因此保留并诚实报告，但不把它们
与内容盲评混成一个结论，也不通过补无意义 citation 或调权让 ReasFlow 的 `/40` 反转。

### 6.2 匿名内容评测

| 任务 | ReasFlow 总体票 | Pure 总体票 | Tie | 任务结论 |
|---|---:|---:|---:|---|
| Extragradient | 2 | 1 | 0 | ReasFlow 胜 |
| Error Feedback | 3 | 0 | 0 | ReasFlow 胜 |
| 合计 | 5 | 1 | 0 | ReasFlow 任务级 2/2 胜 |

两题 54 个维度票合计：ReasFlow `32`、Pure Codex `13`、Tie `9`。

| 维度 | Pure | ReasFlow | Tie | 当前解释 |
|---|---:|---:|---:|---|
| Taxonomy | 3 | 1 | 2 | Codex 原生强项，应避免模板干预 |
| Research lineage | 0 | 4 | 2 | ReasFlow 原始来源与关系限定有效 |
| Timeline | 5 | 1 | 0 | Codex 原生明显更强 |
| Comparative synthesis | 4 | 1 | 1 | Codex 原生更强 |
| Paper detail | 0 | 5 | 1 | ReasFlow 的具体 evidence 边界有效 |
| Pedagogical clarity | 0 | 5 | 1 | 薄增强未破坏主线，并改善可信度 |
| Gap grounding | 1 | 4 | 1 | later work/scope 检查产生优势 |
| Counterevidence | 0 | 6 | 0 | ReasFlow 最稳定优势 |
| Future work | 0 | 5 | 1 | 从未解决 scope 推导 testable direction |

## 7. 文章 PDF

### Extragradient

- Pure Codex：
  `/home/iceysakura/lab/paper_gen/reasflow-workspaces/runs/2026-08-27-reasflow-minimal-parity-v1/extragradient_methods/pure-codex/extragradient_methods__survey__pure-codex__Codex-WebSearch.pdf`
- Minimal ReasFlow：
  `/home/iceysakura/lab/paper_gen/reasflow-workspaces/runs/2026-08-27-reasflow-minimal-parity-v1/extragradient_methods/reasflow-s2/extragradient_methods__survey__reasflow-s2__ReasFlow-CodexFirst.pdf`

### Error Feedback

- Pure Codex：
  `/home/iceysakura/lab/paper_gen/reasflow-workspaces/runs/2026-08-27-reasflow-minimal-parity-v2/error_feedback/pure-codex/error_feedback__survey__pure-codex__Codex-WebSearch.pdf`
- Minimal ReasFlow：
  `/home/iceysakura/lab/paper_gen/reasflow-workspaces/runs/2026-08-27-reasflow-minimal-parity-v2/error_feedback/reasflow-s2/error_feedback__survey__reasflow-s2__ReasFlow-CodexFirst.pdf`

四份 PDF 均已编译并检查首页署名、题目、cutoff、页数和非空文件：Extragradient 为 30/21
页，Error Feedback 为 28/24 页。

## 8. 当前设计边界与下一准入门槛

当前不应因为已有优势又恢复复杂流程。正确方向是继续保持：

```text
Codex native planning / research / synthesis / prose
                         +
minimal cited-only evidence and publication postflight
```

ReaScholar 后续只能作为可选 evidence layer，用于 9 维 tag、citation relation、paper profile、
later work、counterevidence 和 open-problem evidence；不能把 Domain/category/timeline 直接写成
文章结构。

当前只有两个开发题。恢复 ReaScholar 和其他低优先级工作前，应在至少四个冻结留出题上
确认任务级 `ReasFlow >= Pure Codex`，且不能只看 reviewer 数量，统计单位必须是任务。
