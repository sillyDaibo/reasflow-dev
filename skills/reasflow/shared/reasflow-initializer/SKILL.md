---
name: reasflow-initializer
description: Use when the user asks Codex to initialize, set up, convert, or bootstrap a folder/workspace/project as a reasflow project, or asks how an agent should install reasflow into the current directory.
---

# Reasflow Initializer

## Goal

Initialize a target folder as a reasflow Codex project by running the reasflow-dev local installer from that folder.

Global reasflow-dev installation only makes reusable agents and shared skills available. It does not write project-level `.codex/config.toml`, so it does not turn the current project into a reasflow project.

## Workflow

1. Identify the target project root. If the user says "this folder" or "current project", use the current working directory.
2. Check for existing reasflow files:
   ```bash
   find . -maxdepth 3 \( -path './.codex/config.toml' -o -path './.codex/agents' -o -path './.agents/skills' -o -path './.codex/reasflow-skills' \) -print
   ```
3. If no conflicting reasflow targets exist, run the local installer from the target root:
   ```bash
   curl -fsSL https://raw.githubusercontent.com/sillyDaibo/reasflow-dev/main/install.sh | bash
   ```
4. If targets already exist and the user wants to refresh/replace them, run:
   ```bash
   curl -fsSL https://raw.githubusercontent.com/sillyDaibo/reasflow-dev/main/install.sh | bash -s -- --force
   ```
5. Tell the user to restart Codex in that project so `.codex/config.toml`, `.codex/agents/`, and `.agents/skills/` are reloaded.

## Local Source Checkout

When working inside or near a checked-out `reasflow-dev` repository, prefer installing from that checkout instead of downloading from GitHub:

```bash
REASFLOW_DEV_SOURCE_DIR=/path/to/reasflow-dev bash /path/to/reasflow-dev/install.sh
```

Use `--force` only when replacing existing installed reasflow targets is intended.

## Expected Result

After local initialization, the target project should contain:

```text
.agents/skills/
.codex/agents/
.codex/config.toml
.codex/reasflow-skills/
.reasflow-dev/manifest.txt
```

For a reusable global install, use:

```bash
curl -fsSL https://raw.githubusercontent.com/sillyDaibo/reasflow-dev/main/install.sh | bash -s -- --global
```

This installs shared resources under the user's home directory, but each reasflow project still needs local initialization.
