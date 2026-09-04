# Spec-driven development (GraphSPEC)

This repo uses the GraphSPEC Copilot-native spec-driven development (SDD)
workflow, backed by a local `copilot-graph-spec` MCP server (installed as a
Python package, not vendored in this repo) that serves a unified code + spec
graph.

## Workflow

`constitution → specify → plan → tasks → analyze → implement`, one feature
at a time under `spec/features/<slug>/`, governed by
[spec/constitution.md](../spec/constitution.md). Stages after `constitution`
are automated via `.github/agents/*.agent.md` + `.github/prompts/*.prompt.md`
— prefer those over ad-hoc spec/plan/tasks edits. Start a new feature with
`/specify`, or invoke `spec`/`plan`/`tasks`/`analyze`/`implement` directly.

## Graph MCP server

The `copilot-graph-spec` server is registered in [.vscode/mcp.json](../.vscode/mcp.json)
and must be started once from VS Code's MCP view before agents can use the
`graph_*` tools. If the index looks stale, rebuild it from the repo root:

```bash
copilot-graph-spec index .    # rebuild .graph/graph.db
copilot-graph-spec embed       # populate embeddings for hybrid search
```

See [graph-usage.instructions.md](instructions/graph-usage.instructions.md)
for when to prefer graph queries over reading whole files.
