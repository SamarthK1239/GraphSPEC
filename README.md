# GraphSPEC

Copilot-native spec-driven development (SDD) workflow — `constitution →
specify → plan → tasks → analyze → implement` — backed by a local **Python
MCP server** that serves a **unified graph** of your code structure *and*
spec/artifact traceability.

The differentiator is context efficiency: agents query the graph for
*pointers* (path + line span + signature) and fetch only the exact spans
they need via `graph_read_span` — they never read whole files. That's what
keeps context small on large projects.

## Features

- **8 `graph_*` MCP tools** for pointer-based code + spec exploration
  (search, outline, symbol lookup, neighbors, impact/blast-radius, subgraph,
  exact-span reads, spec↔code traceability).
- **Hybrid search** — FTS5 lexical search, upgraded to lexical + semantic
  (sqlite-vec, fused via reciprocal-rank fusion) once embeddings are computed.
- **Language-agnostic indexing** via tree-sitter (Python, JavaScript,
  TypeScript, TSX out of the box; pluggable for more).
- **Traceability graph** over `spec → requirement → plan_item → task`, with
  automatic coverage-gap detection (`graph_trace`).
- **Incremental indexing** (content-hash based) and an optional polling
  `watch` mode that keeps the index and embeddings continuously up to date.
- **5-stage SDD workflow** (`spec`/`plan`/`tasks`/`analyze`/`implement`)
  implemented as VS Code custom agents + prompts, wired to the graph tools.

## Quick Start

```bash
cd graph_mcp
uv pip install -e ".[dev]"        # or: pip install -e ".[dev]"

uv run graph-mcp index ..         # build .graph/graph.db from the repo root
uv run graph-mcp embed            # populate embeddings for hybrid search
uv run graph-mcp serve            # run the MCP server over stdio
```

The server is already registered in [.vscode/mcp.json](.vscode/mcp.json).
Start it once from VS Code's MCP view (or Command Palette) so chat agents in
this workspace can use the graph tools live.

## CLI

| Command | Purpose |
| --- | --- |
| `graph-mcp index [ROOT] [--db PATH] [--incremental]` | Build (or incrementally update) the graph database |
| `graph-mcp embed [--db PATH] [--backend NAME] [--model NAME] [--force]` | Compute embeddings for hybrid search |
| `graph-mcp watch [ROOT] [--db PATH] [--interval N]` | Poll for changes; incrementally re-index + re-embed |
| `graph-mcp serve [--root PATH] [--db PATH]` | Run the MCP server over stdio |
| `graph-mcp --version` | Print the installed version |

## MCP Tools

| Tool | Purpose |
| --- | --- |
| `graph_search` | Hybrid lexical + semantic search over symbols/files/spec artifacts |
| `graph_file_outline` | Symbol map of a file, no bodies |
| `graph_get_symbol` | Signature / doc / location only |
| `graph_neighbors` | Callers / callees / imports / references of a symbol |
| `graph_impact` | Blast radius of changing X (powers plan/tasks) |
| `graph_subgraph` | Focused, token-budgeted slice for a single task |
| `graph_read_span` | Fetch an exact line range on demand |
| `graph_trace` | spec ↔ requirement ↔ task ↔ symbol traceability + coverage gaps |

## Architecture

- `graph_mcp/src/graph_mcp/indexer` — tree-sitter code parsing + the
  `spec/features/**` markdown parser, both incremental-aware.
- `graph_mcp/src/graph_mcp/embeddings` — pluggable embedder (`fastembed`
  default, `sentence-transformers` opt-in via the `[torch]` extra).
- `graph_mcp/src/graph_mcp/db` — SQLite schema/connection helpers.
- `graph_mcp/src/graph_mcp/mcp_server` — the 8 `graph_*` tool implementations.
- `graph_mcp/src/graph_mcp/cli` — the `graph-mcp` command line entry point.

**SQLite schema:** `nodes(id, type, path, name, signature, line_start,
line_end, hash, meta)` · `edges(src, dst, type)` · `nodes_fts` (FTS5 lexical
index) · `vec_nodes` (sqlite-vec embeddings) · `indexed_files` (mtime/hash
bookkeeping for incremental indexing).

**Node types:** `file | symbol | spec | requirement | plan_item | task`
**Edge types:** `imports | calls | references | contains | derives |
implements | covers | depends_on`

## Spec-Driven Workflow

`constitution → specify → plan → tasks → analyze → implement`, one feature
at a time under `spec/features/<slug>/`, governed by
[spec/constitution.md](spec/constitution.md) (including the `REQ-<NNN>` /
`PLAN-<NNN>` / `TASK-<NNN>` traceability convention the graph parser relies
on). The last five stages are implemented as custom agents/prompts under
[.github/agents](.github/agents) and [.github/prompts](.github/prompts);
start a new feature with `/specify`, or invoke `spec`/`plan`/`tasks`/
`analyze`/`implement` directly.

See [spec/features/cli-version-flag/](spec/features/cli-version-flag/) for a
complete worked example (spec → plan → tasks → analyze → implement) that
added the `--version` flag above.

## Directory Layout

```
.github/
  copilot-instructions.md
  instructions/graph-usage.instructions.md   # always-on: prefer graph queries
  agents/{spec,plan,tasks,implement,analyze}.agent.md
  prompts/{specify,plan,tasks,implement,analyze}.prompt.md
spec/
  constitution.md
  templates/{spec,plan,tasks,research}.template.md
  features/<slug>/{spec.md,plan.md,tasks.md,research.md}
graph_mcp/
  pyproject.toml
  src/graph_mcp/{indexer,mcp_server,cli,db,embeddings}
  tests/
.graph/graph.db            # generated index (gitignored)
.vscode/mcp.json           # registers stdio server (uv run graph-mcp serve)
scripts/                   # index / refresh / validate helpers
```

## Development

```bash
cd graph_mcp
uv run pytest       # full test suite
```

## Status

v1 implemented. See [PLANNING.md](PLANNING.md) for the locked design
decisions, phased build history, and verification methodology.

 