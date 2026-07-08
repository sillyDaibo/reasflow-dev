# No-Restart Reasflow Execution

Use only when the project was just initialized and the user explicitly wants to run reasflow before restarting Codex.

Codex does not hot reload `.codex/config.toml`, `.codex/agents/`, or newly installed skills. Restarting Codex is preferred.

## Rule

- The current main agent must read `.codex/config.toml` first, then its own `.codex/agents/<agent>.toml`.
- Subagents must not read `.codex/config.toml`.
- Every subagent prompt must tell that subagent to read only its own `.codex/agents/<subagent>.toml`.
- Prefer project-local `.codex/agents/*.toml`; use `~/.codex/agents/*.toml` only if the project-local file is absent.

## Main Prompt Prefix

```text
You are <agent-name>. Before doing any task work, read .codex/config.toml to understand the project's reasflow orchestration rules, then read <agent-toml-path> to understand your identity, developer instructions, mounted skills, and workflow. Follow those files as authoritative for this task, with the agent TOML defining your specific role.

If you spawn or resume any reasflow subagent, do not ask it to read .codex/config.toml. Identify that subagent's TOML file, and prepend its prompt with: "You are <subagent-name>. Before doing any task work, read <subagent-toml-path> to understand your identity, developer instructions, mounted skills, and workflow. Follow that TOML role file as authoritative for this task."
```

Append the user's actual task after this prefix.

## Child Prompt Prefix

```text
You are <subagent-name>. Before doing any task work, read <subagent-toml-path> to understand your identity, developer instructions, mounted skills, and workflow. Follow that TOML role file as authoritative for this task.
```

After the immediate task finishes, tell the user to restart Codex before continuing normal reasflow work.
