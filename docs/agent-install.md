# Reasflow Agent Installation Guide

Use this guide when a user asks you to install or update reasflow-dev globally for Codex.

## Goal

Install the reusable reasflow Codex skills and agents globally so future Codex sessions can discover `reasflow-initializer` and initialize individual folders as reasflow projects.

Global installation writes to the user's home directory:

```text
~/.agents/skills/
~/.codex/reasflow-skills/
~/.codex/agents/
```

It does not write `~/.codex/config.toml`, and it does not turn the current folder into a reasflow project. Project initialization is a separate local install run from the target project root.

## Unix or macOS

Install or update globally:

```bash
curl -fsSL https://raw.githubusercontent.com/sillyDaibo/reasflow-dev/main/install.sh | bash -s -- --global
```

If an existing reasflow-dev-managed target blocks the install and the user wants to replace it, rerun with `--force`:

```bash
curl -fsSL https://raw.githubusercontent.com/sillyDaibo/reasflow-dev/main/install.sh | bash -s -- --global --force
```

## Windows PowerShell

Install or update globally:

```powershell
& ([scriptblock]::Create((irm https://raw.githubusercontent.com/sillyDaibo/reasflow-dev/main/install.ps1))) -Global
```

If an existing reasflow-dev-managed target blocks the install and the user wants to replace it, rerun with `-Force`:

```powershell
& ([scriptblock]::Create((irm https://raw.githubusercontent.com/sillyDaibo/reasflow-dev/main/install.ps1))) -Global -Force
```

## Verify

Check that the global initializer skill exists:

```bash
test -f "$HOME/.agents/skills/reasflow-initializer/SKILL.md"
```

On Windows PowerShell:

```powershell
Test-Path "$env:USERPROFILE\.agents\skills\reasflow-initializer\SKILL.md"
```

Tell the user to restart Codex after installation so the global skills and agents are reloaded.

## Initialize a Project Later

After global installation, the user can ask Codex:

```text
Initialize this folder as a reasflow project.
```

The `reasflow-initializer` skill tells Codex to run the local installer from the target project root.
