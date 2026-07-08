# No-Restart Reasflow Execution

Use this only when the target project has just been initialized as reasflow and the user explicitly wants to run reasflow before restarting Codex.

Codex does not hot reload `.codex/config.toml`, `.codex/agents/`, or newly installed skills. The workaround is to manually bootstrap the current main agent from project config, and bootstrap every reasflow subagent from its own TOML role file before doing task work.

## Preconditions

Run from the initialized project root.

Required files:

```text
.codex/agents/
.codex/config.toml
.codex/reasflow-skills/
.agents/skills/
```

If these files are missing, initialize the project first. If the user can restart Codex, stop and ask them to restart instead of using this workaround.

## Agent TOML Resolution

Prefer project-local TOML files:

```text
.codex/agents/<agent-name>.toml
```

Use global TOML files only if the project-local file is absent:

```text
~/.codex/agents/<agent-name>.toml
```

Do not assume an identity from memory. The current main agent reads `.codex/config.toml`; every dispatched subagent reads only its own TOML file.

## Main Agent Project Config

The current main agent must read project config first:

```text
.codex/config.toml
```

This project config contains the reasflow meta-orchestrator instructions and global workflow constraints for the main agent. Do not require subagents to read `.codex/config.toml`; their role is defined by their own TOML files.

## Main Agent Prompt Prefix

Prepend this to the current main agent task prompt:

```text
You are <agent-name>. Before doing any task work, read .codex/config.toml to understand the project's reasflow orchestration rules, then read <agent-toml-path> to understand your identity, developer instructions, available mounted skills, and workflow. Follow those files as authoritative for this task, with the agent TOML defining your specific role.

If you spawn or resume any reasflow subagent, do not ask it to read .codex/config.toml. Identify that subagent's TOML file, and prepend its prompt with "You are <subagent-name>. Before doing any task work, read <subagent-toml-path> to understand your identity, developer instructions, available mounted skills, and workflow. Follow that TOML role file as authoritative for this task."
```

Then append the actual user task.

## Examples

Survey:

```text
You are survey. Before doing any task work, read .codex/config.toml to understand the project's reasflow orchestration rules, then read .codex/agents/survey.toml to understand your identity, developer instructions, available mounted skills, and workflow. Follow those files as authoritative for this task, with the agent TOML defining your specific role.

If you spawn or resume any reasflow subagent, do not ask it to read .codex/config.toml. Identify that subagent's TOML file, and prepend its prompt with "You are <subagent-name>. Before doing any task work, read <subagent-toml-path> to understand your identity, developer instructions, available mounted skills, and workflow. Follow that TOML role file as authoritative for this task."

Task: Conduct a literature review on <topic>.
```

Prover:

```text
You are prover. Before doing any task work, read .codex/config.toml to understand the project's reasflow orchestration rules, then read .codex/agents/prover.toml to understand your identity, developer instructions, available mounted skills, and workflow. Follow those files as authoritative for this task, with the agent TOML defining your specific role.

If you spawn or resume any reasflow subagent, do not ask it to read .codex/config.toml. Identify that subagent's TOML file, and prepend its prompt with "You are <subagent-name>. Before doing any task work, read <subagent-toml-path> to understand your identity, developer instructions, available mounted skills, and workflow. Follow that TOML role file as authoritative for this task."

Task: Prove convergence for the algorithm in Alg_Exp/document/pseudocode.tex.
```

## Subagent Dispatch Rule

When a bootstrapped reasflow agent starts another reasflow agent, the child prompt must include the TOML-only role-bootstrap prefix for the child role. The child should not read `.codex/config.toml`.

Examples:

- `survey` spawning `survey-outline`: child reads `.codex/agents/survey-outline.toml`.
- `survey` spawning `survey-section-writer`: child reads `.codex/agents/survey-section-writer.toml`.
- `survey` spawning `survey-related-works`: child reads `.codex/agents/survey-related-works.toml`.
- `prover` spawning `lemma-prover`: child reads `.codex/agents/lemma-prover.toml`.
- `prover` spawning `lemma-verifier`: child reads `.codex/agents/lemma-verifier.toml`.
- `paper` spawning `paper-subwriter`: child reads `.codex/agents/paper-subwriter.toml`.
- `paper` spawning `latex-writer`: child reads `.codex/agents/latex-writer.toml`.

## Safety

This workaround is less reliable than restarting Codex because the current session still has old project config in memory. Prefer restart whenever possible.

After the immediate task finishes, tell the user to restart Codex before continuing normal reasflow work.
