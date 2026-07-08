# No-Restart Reasflow Execution

Use this only when the target project has just been initialized as reasflow and the user explicitly wants to run reasflow before restarting Codex.

Codex does not hot reload `.codex/config.toml`, `.codex/agents/`, or newly installed skills. The workaround is to manually bootstrap the current reasflow role and every reasflow subagent by telling it to read the installed project config and TOML role file before doing any task work.

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

Do not assume an identity from memory. Read `.codex/config.toml` and the TOML file for every reasflow agent you start.

## Project Config

Every no-restart reasflow prompt must instruct the agent to read project config first:

```text
.codex/config.toml
```

This project config contains the reasflow meta-orchestrator instructions and global workflow constraints.

## Prompt Prefix

Prepend this to every reasflow agent prompt:

```text
You are <agent-name>. Before doing any task work, read .codex/config.toml to understand the project's reasflow orchestration rules, then read <agent-toml-path> to understand your identity, developer instructions, available mounted skills, and workflow. Follow those files as authoritative for this task, with the agent TOML defining your specific role.

If you spawn or resume any reasflow subagent, you must apply the same bootstrap rule: identify that subagent's TOML file, and prepend its prompt with "You are <subagent-name>. Before doing any task work, read .codex/config.toml to understand the project's reasflow orchestration rules, then read <subagent-toml-path> to understand your identity, developer instructions, available mounted skills, and workflow. Follow those files as authoritative for this task, with the agent TOML defining your specific role."
```

Then append the actual user task.

## Examples

Survey:

```text
You are survey. Before doing any task work, read .codex/config.toml to understand the project's reasflow orchestration rules, then read .codex/agents/survey.toml to understand your identity, developer instructions, available mounted skills, and workflow. Follow those files as authoritative for this task, with the agent TOML defining your specific role.

If you spawn or resume any reasflow subagent, you must apply the same bootstrap rule: identify that subagent's TOML file, and prepend its prompt with "You are <subagent-name>. Before doing any task work, read .codex/config.toml to understand the project's reasflow orchestration rules, then read <subagent-toml-path> to understand your identity, developer instructions, available mounted skills, and workflow. Follow those files as authoritative for this task, with the agent TOML defining your specific role."

Task: Conduct a literature review on <topic>.
```

Prover:

```text
You are prover. Before doing any task work, read .codex/config.toml to understand the project's reasflow orchestration rules, then read .codex/agents/prover.toml to understand your identity, developer instructions, available mounted skills, and workflow. Follow those files as authoritative for this task, with the agent TOML defining your specific role.

If you spawn or resume any reasflow subagent, you must apply the same bootstrap rule: identify that subagent's TOML file, and prepend its prompt with "You are <subagent-name>. Before doing any task work, read .codex/config.toml to understand the project's reasflow orchestration rules, then read <subagent-toml-path> to understand your identity, developer instructions, available mounted skills, and workflow. Follow those files as authoritative for this task, with the agent TOML defining your specific role."

Task: Prove convergence for the algorithm in Alg_Exp/document/pseudocode.tex.
```

## Subagent Dispatch Rule

When a bootstrapped reasflow agent starts another reasflow agent, the child prompt must include the same role-bootstrap prefix for the child role.

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
