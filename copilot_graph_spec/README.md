# copilot-graph-spec

Copilot-native spec-driven development (SDD) workflow — `constitution →
specify → plan → tasks → analyze → implement` — backed by a local **Python
MCP server** that serves a **unified graph** of your code structure *and*
spec/artifact traceability.

The differentiator is context efficiency: agents query the graph for
*pointers* (path + line span + signature) and fetch only the exact spans
they need via `graph_read_span` — they never read whole files. That's what
keeps context small on large projects.

## Install

```bash
pip install copilot-graph-spec        # or: uv tool install copilot-graph-spec
cd /path/to/your-project
copilot-graph-spec init                # scaffold .vscode/mcp.json, .github/{agents,prompts,
                                       # instructions}, spec/{constitution.md,templates}
copilot-graph-spec index .             # build .graph/graph.db
copilot-graph-spec embed               # populate embeddings for hybrid search
```

## What you get

- **8 `graph_*` MCP tools** for pointer-based code + spec exploration
  (search, outline, symbol lookup, neighbors, impact/blast-radius, subgraph,
  exact-span reads, spec↔code traceability).
- **Hybrid search** — FTS5 lexical, fused with sqlite-vec semantic search
  (reciprocal-rank fusion) once embeddings are computed.
- **Language-agnostic indexing** via tree-sitter (Python, JavaScript,
  TypeScript, TSX out of the box; pluggable for more).
- **Traceability graph** over `spec → requirement → plan_item → task`, with
  automatic coverage-gap detection.
- **Incremental indexing** and a polling `watch` mode.
- **5-stage SDD workflow** as VS Code custom agents + prompts, wired to the
  graph tools.

Full documentation, architecture, CLI reference, and the user manual live
in the [GitHub repository](https://github.com/SamarthK1239/GraphSPEC) —
see the [README](https://github.com/SamarthK1239/GraphSPEC#readme) and
[docs/USER_GUIDE.md](https://github.com/SamarthK1239/GraphSPEC/blob/main/docs/USER_GUIDE.md).

Licensed under [MIT](https://github.com/SamarthK1239/GraphSPEC/blob/main/LICENSE).
