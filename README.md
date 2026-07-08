# reasflow-dev

`reasflow-dev` 是一个纯资源仓库，只提供给 Codex 使用的：

- `skills/`
- `agents/`
- 安装脚本

这里没有 Rust 代码，没有 `opencode`，也不需要构建。

## Installation

### For Humans

把这段话复制给 Codex、Claude Code、Cursor 或其它能运行 shell 的 agent：

```text
Install or update reasflow-dev globally for Codex by following this guide:
https://raw.githubusercontent.com/sillyDaibo/reasflow-dev/main/docs/agent-install.md
```

装好以后，重启 Codex。之后在任意目标项目里对 Codex 说：

```text
Initialize this folder as a reasflow project.
```

### What This Does

全局安装会让 Codex 以后自动发现 `reasflow-initializer` skill。这个 skill 会告诉 Codex 如何把某个具体文件夹初始化成 reasflow 项目。

全局安装写入：

- `~/.agents/skills/`
- `~/.codex/reasflow-skills/`
- `~/.codex/agents/`

项目初始化写入目标项目：

- `./.agents/skills/`
- `./.codex/reasflow-skills/`
- `./.codex/agents/`
- `./.codex/config.toml`

### For Agents

Fetch the guide and follow it step by step:

```bash
curl -fsSL https://raw.githubusercontent.com/sillyDaibo/reasflow-dev/main/docs/agent-install.md
```

### Manual Install

Unix/macOS global install:

```bash
curl -fsSL https://raw.githubusercontent.com/sillyDaibo/reasflow-dev/main/install.sh | bash -s -- --global
```

Windows PowerShell global install:

```powershell
& ([scriptblock]::Create((irm https://raw.githubusercontent.com/sillyDaibo/reasflow-dev/main/install.ps1))) -Global
```

Local project install:

```bash
curl -fsSL https://raw.githubusercontent.com/sillyDaibo/reasflow-dev/main/install.sh | bash
```

Dev mode keeps a git checkout and installs symlinks:

```bash
curl -fsSL https://raw.githubusercontent.com/sillyDaibo/reasflow-dev/main/install.sh | bash -s -- --dev
```

## 设计

默认设计只有三件事：

1. 默认 `local`
2. 默认不依赖 `git`
3. 默认直接可用，不污染全局环境

安装脚本只暴露三个主要开关：

- `--global`
- `--dev`
- `--force`

## 目录

```text
reasflow-dev/
├── agents/
├── skills/
├── install.sh
├── install.ps1
└── README.md
```

## 推荐约定

推荐把 skill 当作 **按 agent 显式挂载** 的资源，而不是先全量暴露再逐个排除。

- `agents/*.toml` 里只保留这个 agent 真正需要的 `[[skills.config]]`
- 不要把项目私有 skill 同时写进全局 `~/.codex/config.toml`
- 共享 skill 放进默认扫描根目录，供多个 agent 复用
- 私有 skill 放进非默认扫描目录，只通过 agent 显式挂载

推荐分层方式：

```text
skills/
└── reasflow/
    ├── shared/
    │   ├── asset-inventory/
    │   ├── citation-hygiene/
    │   └── workspace-conventions/
    ├── common/
    │   ├── interactive-vs-auto-execution/
    │   └── workspace-cartography/
    ├── intro/
    │   ├── introduction-framing/
    │   └── abstract-alignment/
    ├── paper/
    │   ├── chapter-writing/
    │   └── csiam/
    ├── prover/
    │   ├── knowledge-card-retrieval/
    │   └── reference-download/
    ├── survey/
    │   ├── autosurvey-execution/
    │   ├── autosurvey-paper-retrieval/
    │   └── survey-tex-bib-packaging/
    ├── experiment/
    │   └── smart-plotting/
    └── algorithm/
        └── toy-verification/
```

安装后会拆成两棵树：

```text
.agents/skills/<shared-skill>/
.codex/reasflow-skills/<category>/<private-skill>/
```

也就是说：

- 共享 skill 会自动被扫描
- 私有 skill 必须在 agent 配置里显式引用，例如：

```toml
path = "../../.codex/reasflow-skills/prover/knowledge-card-retrieval/SKILL.md"
```

这样才能真正实现“只有某几个 agent 知道某些私有 skill”。

当前仓库里的 agent 配置也遵循这个方向：默认只正向声明需要的少量 skill。`enabled = true` 是 Codex agent role schema 要求的顶层字段，不用于控制单个 skill。

## 更新

最简单的更新方式就是重新运行同一条安装命令。

如果之前用的是 `--dev`，重新执行安装脚本也会刷新本地 clone 并保持链接关系。

## 冲突处理

如果目标位置已经存在同名 `skill` 或 `agent`，安装器默认停止。

明确要覆盖时再传：

```bash
./install.sh --force
```

## 内容说明

- `agents/*.toml` 是给 Codex 的自定义 agents
- `skills/*/SKILL.md` 是给 Codex 的 project/global skills
- 若某些老 prompt 里原本依赖 `$PACK_ROOT`，这里已经统一改为安装后的 skill 根目录解析方式
- 补了少量兼容脚本，避免旧 agent 指向缺失入口
