---
name: workspace-conventions
description: Conventions for tools, skills, and project state in ReasLab workspaces.
---

## Installed Root

Resolve the installed reasflow-dev skills root before running packaged scripts:

```bash
REASFLOW_SKILLS_ROOT="${REASFLOW_SKILLS_ROOT:-}"
if [ -z "$REASFLOW_SKILLS_ROOT" ]; then
  if [ -d ./.agents/skills ]; then
    REASFLOW_SKILLS_ROOT="$(pwd)/.agents/skills"
  elif [ -d "$HOME/.agents/skills" ]; then
    REASFLOW_SKILLS_ROOT="$HOME/.agents/skills"
  else
    echo "reasflow-dev skills not found in ./.agents/skills or $HOME/.agents/skills" >&2
    exit 1
  fi
fi
```

## Tools

Standard shell tools are available in PATH. Use them directly.

- Build Lean projects: `lake build`, `lake build Mathlib.Order.Basic`
- Compile LaTeX documents: `latexmk`
- Run Python: use `python-execute` (in PATH; run `python-execute --help` for all options), not `python3`/`uv`/`pip`
- Search code: `rg`, `fd`, `jq`, `grep`, `find`
- Open a file in the web UI: `open main.pdf`

After compiling LaTeX, run `open main.pdf` to show the PDF
in the user's browser.

When the user asks to use MCP, or asks to compile LaTeX or
build Lean via MCP, just run the command directly (`latexmk`,
`lake build`, etc.). All tools are standard shell commands.

### python-execute

`python-execute` is the CLI for running Python in the runtime container.
Invoke it through the shell/terminal tool like any other command.

All Python-related commands (`python3`, `uv`, `pip`, etc.) MUST go through
`python-execute` — never run them directly via the shell tool.

The runtime container has solver packages and their licenses pre-configured
(gurobipy, coptpy, mosek, cplex, ortools, pulp, etc.). Do not attempt to
install, activate, or configure licenses yourself — they are already set up.

Pre-installed packages: numpy, scipy, pandas, matplotlib, gurobipy, coptpy,
mosek, cplex, ortools, pulp, etc.

- `python-execute -c 'print(1+1)'` — run inline code
- `python-execute script.py` — run a file
- `python-execute install <pkg>` — install a package
- `python-execute remove <pkg>` — remove a package
- `python-execute list-packages` — list installed packages
- `python-execute env-status` — check environment and available packages
- `python-execute history` — query execution history
- `python-execute stop <id>` — stop a running execution

## Skills

Skills are markdown files with YAML frontmatter (name, description).

- Built-in skills: ./.agents/skills/ (packaged in agent image)
- Project skills: ./.agents/skills/
