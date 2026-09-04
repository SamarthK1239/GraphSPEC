---
description: "Always-on: prefer copilot-graph-spec's graph_* queries over reading whole files for source code exploration."
applyTo: "**"
---

# Graph-First Code Exploration

When `copilot-graph-spec` MCP tools are available, use them instead of opening whole
source files:

1. **Locate** with `graph_search` (or `graph_file_outline` / `graph_get_symbol`
   / `graph_neighbors` / `graph_impact` / `graph_subgraph`) to get pointers —
   path + line span + signature — never whole file contents.
2. **Fetch** only the exact span you need via `graph_read_span`.
3. Re-run search/outline before assuming a symbol doesn't exist — don't guess.

This applies to *source code* exploration only. Reading/editing
`spec/**/*.md` (the spec/plan/tasks deliverables themselves) uses the normal
file tools, since those aren't part of the code graph until `copilot-graph-spec index`
runs.

If the graph looks stale (missing recent changes), rebuild it from the repo
root: `copilot-graph-spec index . && copilot-graph-spec embed`.
