# GraphSPEC

[![CI](https://github.com/SamarthK1239/GraphSPEC/actions/workflows/ci.yml/badge.svg)](https://github.com/SamarthK1239/GraphSPEC/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

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

### Adding `graph-mcp` to an existing project

```bash
pip install graph-spec                # or: uv tool install graph-spec
cd /path/to/your-project
graph-mcp init                       # scaffolds .vscode/mcp.json, .github/{agents,prompts,
                                      # instructions}, spec/{constitution.md,templates},
                                      # .graph-mcp.toml and a .gitignore entry for .graph/
graph-mcp index .                    # build .graph/graph.db
graph-mcp embed                      # populate embeddings for hybrid search
```

`init` never overwrites files that already exist (pass `--force` to overwrite).
Open the project in VS Code and start the `graph-mcp` server once from the MCP
view/Command Palette — see **Troubleshooting** below.

### Developing GraphSPEC itself

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

### Troubleshooting

- **MCP tools aren't showing up in chat.** The server is registered but not
  auto-started on first open — open VS Code's MCP view (Command Palette →
  "MCP: List Servers") and start `graph-mcp` manually. Re-running the
  `serve` command by hand (`graph-mcp serve` / `uv run graph-mcp serve`)
  should also succeed with no error if the install is healthy.
- **`.vscode/mcp.json` fails to start with `uv` errors.** The scaffolded
  config for adopted projects invokes the installed `graph-mcp` console
  script directly (no `uv` dependency); only *this* repo's own `.vscode/mcp.json`
  requires `uv` (since it builds `graph-mcp` from source in `graph_mcp/`).

## Editor & client support

The 8 `graph_*` MCP tools are client-agnostic — any MCP-compatible host
(VS Code, Claude Desktop, etc.) can use them once `graph-mcp serve` is
registered. The 5-stage SDD workflow (`.github/agents/*.agent.md` +
`.github/prompts/*.prompt.md`) uses VS Code's Copilot custom-agent format
specifically — other MCP hosts get the graph tools but not that workflow.

## CLI

| Command | Purpose |
| --- | --- |
| `graph-mcp index [ROOT] [--db PATH] [--incremental]` | Build (or incrementally update) the graph database |
| `graph-mcp embed [--db PATH] [--backend NAME] [--model NAME] [--force]` | Compute embeddings for hybrid search |
| `graph-mcp watch [ROOT] [--db PATH] [--interval N]` | Poll for changes; incrementally re-index + re-embed |
| `graph-mcp serve [--root PATH] [--db PATH]` | Run the MCP server over stdio |
| `graph-mcp init [TARGET] [--force]` | Scaffold the SDD workflow + MCP config into an existing project |
| `graph-mcp --version` | Print the installed version |

`index`/`embed`/`watch`/`serve` resolve `ROOT`/`--db` in this order: explicit
flag > nearest `.graph-mcp.toml` (written by `init`, or hand-authored) >
built-in default. See [graph_mcp/src/graph_mcp/config.py](graph_mcp/src/graph_mcp/config.py).

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
  `spec/features/**` markdown parser, both incremental-aware. Adding a
  language means adding a `LanguageConfig` entry to
  [indexer/languages.py](graph_mcp/src/graph_mcp/indexer/languages.py) (a
  code-level extension point today, not a runtime plugin system).
- `graph_mcp/src/graph_mcp/embeddings` — pluggable embedder (`fastembed`
  default, `sentence-transformers` opt-in via the `[torch]` extra).
- `graph_mcp/src/graph_mcp/db` — SQLite schema/connection helpers.
- `graph_mcp/src/graph_mcp/mcp_server` — the 8 `graph_*` tool implementations.
- `graph_mcp/src/graph_mcp/cli` — the `graph-mcp` command line entry point.
- `graph_mcp/src/graph_mcp/config.py` — `.graph-mcp.toml` discovery for
  relocatable `root`/`db` defaults.
- `graph_mcp/src/graph_mcp/init_cmd.py` + `scaffold/` — the bundled
  templates and logic behind `graph-mcp init`.

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

### Retrofitting an existing project

`graph-mcp init` (see Quick Start) drops the same workflow files this repo
uses into any other repo, without vendoring `graph_mcp`'s source: `.vscode/mcp.json`
pointing at the installed console script, `.github/agents`+`prompts`+`instructions`,
`spec/constitution.md`+`templates`, and a `.graph-mcp.toml` so `index`/`embed`/`serve`
work from that repo's own root without extra flags. Run `graph-mcp index . && graph-mcp embed`
afterward, then start a feature with `/specify` as usual.

## Directory Layout

```
.github/
  copilot-instructions.md
  instructions/graph-usage.instructions.md   # always-on: prefer graph queries
  agents/{spec,plan,tasks,implement,analyze}.agent.md
  prompts/{specify,plan,tasks,implement,analyze}.prompt.md
  workflows/{ci,release}.yml
spec/
  constitution.md
  templates/{spec,plan,tasks,research}.template.md
  features/<slug>/{spec.md,plan.md,tasks.md,research.md}
graph_mcp/
  pyproject.toml
  .graph-mcp.toml           # this repo's own root/db config (dogfood)
  src/graph_mcp/{indexer,mcp_server,cli,db,embeddings,config.py,init_cmd.py,scaffold}
  tests/
.graph/graph.db            # generated index (gitignored)
.vscode/mcp.json           # registers stdio server (uv run graph-mcp serve)
scripts/                   # index / refresh / validate helpers
LICENSE
CONTRIBUTING.md
```

## Development

```bash
cd graph_mcp
uv run pytest       # full test suite
```

See [CONTRIBUTING.md](CONTRIBUTING.md) for the release process. Licensed
under [MIT](LICENSE).

## Status

v1 implemented (9 phases, see [PLANNING.md](PLANNING.md)) including this
shareability hardening pass — CI, packaging, `.graph-mcp.toml`, and
`graph-mcp init` for adopting the tool into other projects.

 