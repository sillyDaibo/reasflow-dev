# reasflow-dev

`reasflow-dev` 是一个纯资源仓库，只提供给 Codex 使用的：

- `skills/`
- `agents/`
- 安装脚本

这里没有 Rust 代码，没有 `opencode`，也不需要构建。

## 安装

默认是 **local + release**：

```bash
curl -fsSL https://raw.githubusercontent.com/sillyDaibo/reasflow-dev/main/install.sh | bash
```

这会把内容安装到当前项目：

- `./.agents/skills/reasflow/`
- `./.codex/agents/`

### 全局安装

```bash
curl -fsSL https://raw.githubusercontent.com/sillyDaibo/reasflow-dev/main/install.sh | bash -s -- --global
```

这会安装到：

- `~/.agents/skills/reasflow/`
- `~/.codex/agents/`

### 持续开发模式

如果你想保留一个可 `git pull` 的源码副本并用符号链接联动安装：

```bash
curl -fsSL https://raw.githubusercontent.com/sillyDaibo/reasflow-dev/main/install.sh | bash -s -- --dev
```

也可以配合全局安装：

```bash
curl -fsSL https://raw.githubusercontent.com/sillyDaibo/reasflow-dev/main/install.sh | bash -s -- --dev --global
```

`--dev` 需要本机安装 `git`。默认模式不需要 `git`。

### Windows

默认本地安装：

```powershell
irm https://raw.githubusercontent.com/sillyDaibo/reasflow-dev/main/install.ps1 | iex
```

全局安装：

```powershell
& ([scriptblock]::Create((irm https://raw.githubusercontent.com/sillyDaibo/reasflow-dev/main/install.ps1))) -Global
```

Windows 全局安装默认落到当前用户目录下：

- `$env:USERPROFILE\.codex\agents\`
- `$env:USERPROFILE\.agents\skills\`
- `$env:USERPROFILE\.reasflow-dev\`

开发模式：

```powershell
& ([scriptblock]::Create((irm https://raw.githubusercontent.com/sillyDaibo/reasflow-dev/main/install.ps1))) -Dev
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
- 共享 skill 可以被多个 agent 同时引用
- 私有 skill 只要不被其他 agent 引用，其他 agent 默认就看不到

推荐分层方式：

```text
skills/
└── reasflow/
    ├── shared/
    │   ├── deep-research/
    │   └── workspace-conventions/
    ├── prover/
    │   ├── knowledge-card-retrieval/
    │   └── reference-download/
    ├── survey/
    │   ├── autosurvey-execution/
    │   └── autosurvey-paper-retrieval/
    └── experiment/
        └── smart-plotting/
```

安装后会保留顶层命名空间目录，因此上述结构会落成：

```text
.agents/skills/reasflow/...
```

也就是说 agent 可以直接引用类似：

```toml
path = "../../.agents/skills/reasflow/prover/knowledge-card-retrieval/SKILL.md"
```

当前仓库里的 agent 配置也遵循这个方向：默认只正向声明需要的少量 skill，不再维护大批 `enabled = false` 的排除项。

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
