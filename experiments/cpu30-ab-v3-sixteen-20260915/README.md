# ReasFlow Experiment Agent × Codex Native：16 篇 CPU30 完整实验归档

完整附件：[下载本次 Release](https://github.com/HuangZhengyang-2004/reasflow-dev/releases/tag/cpu30-ab-v3-sixteen-20260915)。归档日期：2026-09-15（Asia/Shanghai）。

本批次是 `cpu30-ab-v3` 的第 003 次运行：16 篇论文、32 个配对运行。A = Codex Native；B = 相同 Codex 基座加载 ReasFlow Experiment Agent。保持原评分与后续核验版本独立，不重新评分或改写实验结果。

归档校验：43,120 个文件；32 条主 trace 的原始哈希全部匹配；34,139 个远端源文件下载校验全部通过。压缩包使用标准 tar 硬链接无损保存重复内容。

## 浏览入口

- [原实验分析总览](analysis/report_overview.md)、[综合分析](analysis/report_synthesis.md)、[机器可读评分](analysis/score_analysis.json)。
- [16 篇算法 Judge 报告](judge-history/judge-cpu30-sixteen-20260915/REPORT.md)：后续固定小实验的数值核验，与原 Midloop / Bigloop 分开解释。
- [完整运行路径索引](RUNS.json)、[原始 trace 校验](inventory/TRACE_VERIFICATION.json)、[逐文件 SHA-256 清单](inventory/MANIFEST.jsonl)。
- `judge-history/` 保留 paper-only、expanded、hardening、sixteen、followup 等已保存版本；其中 followup 是归档时快照，不宣称后续工作已完成。

## 完整附件内容

| 附件 | 内容 |
|---|---|
| local-evidence.tar.gz | 本地工作区证据、全部已保存 Judge 中间轮次/失败记录/审核/对照、论文输入、分析账本、Judge 源码 |
| remote-cpu.tar.gz | 第一台原服务器上的 4 个完整运行：workspace、结果、图表、数据、原 Judge、prompts、配置、logs、原始 session trace、runtime |
| remote-cpu2.tar.gz | 第二台原服务器上的 28 个完整运行，同上 |
| inventory.tar.gz | 文件清单、原始 trace 校验、脱敏与排除明细 |
| SHA256SUMS | 附件校验值 |

将附件解压到同一目录后，`local/` 与 `remote/` 分别保留本地证据和原服务器文件，不相互覆盖。原文件中的绝对路径是历史来源；可通过 RUNS.json 和文件清单定位归档对应文件。

完整归档保留运行的原始 trace（不是截断的可观察事件摘录），以及中间与失败产物。认证文件不上传，日志中识别到的凭据脱敏；可重新安装的虚拟环境、依赖缓存、字节码和系统工具符号链接不作为实验产物上传，明细见 inventory/EXCLUSIONS.json。远端同步也预先排除了 `.git`、`.venv`、`venv`、`site-packages`、`__pycache__`、`.cache`、`cache` 与认证文件。原文件与上传文件的 SHA-256 同时保存在清单中。

## 逐篇原 Judge 分数

分数直接读取原账，Midloop / Bigloop 单独展示；算法核验的通过/差异/未完整判定见独立报告。

| 论文 | Codex Midloop | ReasFlow Midloop | Codex Bigloop | ReasFlow Bigloop | 原 Judge |
|---|---:|---:|---:|---:|---|
| 1811.03761 | 91.53% | 84.18% | 97.22% | 86.11% | [Codex](papers/1811.03761/codex-native/original-judge/) · [ReasFlow](papers/1811.03761/reasflow/original-judge/) |
| 1904.12017 | 83.78% | 84.68% | 44.07% | 45.76% | [Codex](papers/1904.12017/codex-native/original-judge/) · [ReasFlow](papers/1904.12017/reasflow/original-judge/) |
| 2102.06704 | 68.89% | 60.00% | 60.00% | 80.00% | [Codex](papers/2102.06704/codex-native/original-judge/) · [ReasFlow](papers/2102.06704/reasflow/original-judge/) |
| 2111.03820 | 97.73% | 97.73% | 16.13% | 22.58% | [Codex](papers/2111.03820/codex-native/original-judge/) · [ReasFlow](papers/2111.03820/reasflow/original-judge/) |
| 2201.13320 | 68.93% | 80.58% | 30.77% | 23.08% | [Codex](papers/2201.13320/codex-native/original-judge/) · [ReasFlow](papers/2201.13320/reasflow/original-judge/) |
| 2207.04555 | 84.76% | 83.81% | 15.69% | 19.61% | [Codex](papers/2207.04555/codex-native/original-judge/) · [ReasFlow](papers/2207.04555/reasflow/original-judge/) |
| 2212.02387 | 56.52% | 56.52% | 16.67% | 0.00% | [Codex](papers/2212.02387/codex-native/original-judge/) · [ReasFlow](papers/2212.02387/reasflow/original-judge/) |
| 2306.04961 | 71.11% | 58.67% | 14.29% | 0.00% | [Codex](papers/2306.04961/codex-native/original-judge/) · [ReasFlow](papers/2306.04961/reasflow/original-judge/) |
| 2306.05100 | 71.33% | 73.43% | 66.67% | 63.64% | [Codex](papers/2306.05100/codex-native/original-judge/) · [ReasFlow](papers/2306.05100/reasflow/original-judge/) |
| 2309.05204 | 71.74% | 76.09% | 47.06% | 35.29% | [Codex](papers/2309.05204/codex-native/original-judge/) · [ReasFlow](papers/2309.05204/reasflow/original-judge/) |
| 2310.09804 | 83.91% | 80.43% | 34.69% | 26.53% | [Codex](papers/2310.09804/codex-native/original-judge/) · [ReasFlow](papers/2310.09804/reasflow/original-judge/) |
| 2501.04443 | 80.19% | 82.08% | 83.33% | 50.00% | [Codex](papers/2501.04443/codex-native/original-judge/) · [ReasFlow](papers/2501.04443/reasflow/original-judge/) |
| 2501.09516 | 43.69% | 56.31% | 1.21% | 0.40% | [Codex](papers/2501.09516/codex-native/original-judge/) · [ReasFlow](papers/2501.09516/reasflow/original-judge/) |
| 2501.18312 | 57.50% | 72.50% | 71.43% | 71.43% | [Codex](papers/2501.18312/codex-native/original-judge/) · [ReasFlow](papers/2501.18312/reasflow/original-judge/) |
| 2503.07594 | 82.35% | 82.35% | 85.71% | 85.71% | [Codex](papers/2503.07594/codex-native/original-judge/) · [ReasFlow](papers/2503.07594/reasflow/original-judge/) |
| 2504.19004 | 73.55% | 72.73% | 53.66% | 41.46% | [Codex](papers/2504.19004/codex-native/original-judge/) · [ReasFlow](papers/2504.19004/reasflow/original-judge/) |
