# GraphSPEC

Copilot-native spec-driven development workflow backed by a Python MCP server
(`copilot_graph_spec/`) serving a unified code + spec graph. See [README](../README.md)
for architecture and usage, and [PLANNING.md](../PLANNING.md) for locked
design decisions and build history.

## Workflow

`constitution → specify → plan → tasks → analyze → implement`, one feature at
a time under `spec/features/<slug>/`. Governed by [spec/constitution.md](../spec/constitution.md).
Stages after `constitution` are automated via `.github/agents/*.agent.md` +
`.github/prompts/*.prompt.md` — prefer those over ad-hoc spec/plan/tasks edits.

## Build and Test

All commands run from `copilot_graph_spec/` with its `uv`-managed venv:

```bash
uv pip install -e ".[dev]"   # install (pip + venv fallback if uv unavailable)
uv run pytest                # run the test suite
uv run copilot-graph-spec index ..    # (re)build .graph/graph.db from the repo root
uv run copilot-graph-spec embed       # populate embeddings for hybrid search
uv run copilot-graph-spec serve       # run the MCP server over stdio
```

## Architecture

- `copilot_graph_spec/src/copilot_graph_spec/{indexer,embeddings,db,mcp_server,cli}` — parsing,
  embeddings, SQLite storage, the `graph_*` MCP tools, and CLI, respectively.
- Graph nodes/edges follow the schema in the README (`file | symbol | spec |
  requirement | plan_item | task`); prefer graph queries over reading whole
  files where a `copilot-graph-spec` tool is available.
