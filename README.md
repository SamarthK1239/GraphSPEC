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

For the full CLI reference, MCP tool details, configuration options, and
troubleshooting beyond this quickstart, see the
[**User Guide**](docs/USER_GUIDE.md).

### Adding `copilot-graph-spec` to an existing project

```bash
pip install copilot-graph-spec                # or: uv tool install copilot-graph-spec
cd /path/to/your-project
copilot-graph-spec init                # scaffolds .vscode/mcp.json, .github/{agents,prompts,
                                      # instructions}, spec/{constitution.md,templates},
                                      # .copilot-graph-spec.toml and a .gitignore entry for .graph/
copilot-graph-spec index .             # build .graph/graph.db
copilot-graph-spec embed               # populate embeddings for hybrid search
```

`init` never overwrites files that already exist (pass `--force` to overwrite).
Open the project in VS Code and start the `copilot-graph-spec` server once from the MCP
view/Command Palette — see **Troubleshooting** below.

### Developing GraphSPEC itself

```bash
cd copilot_graph_spec
uv pip install -e ".[dev]"        # or: pip install -e ".[dev]"

uv run copilot-graph-spec index ..         # build .graph/graph.db from the repo root
uv run copilot-graph-spec embed            # populate embeddings for hybrid search
uv run copilot-graph-spec serve            # run the MCP server over stdio
```

The server is already registered in [.vscode/mcp.json](.vscode/mcp.json).
Start it once from VS Code's MCP view (or Command Palette) so chat agents in
this workspace can use the graph tools live.

### Troubleshooting

- **MCP tools aren't showing up in chat.** The server is registered but not
  auto-started on first open — open VS Code's MCP view (Command Palette →
  "MCP: List Servers") and start `copilot-graph-spec` manually. Re-running the
  `serve` command by hand (`copilot-graph-spec serve` / `uv run copilot-graph-spec serve`)
  should also succeed with no error if the install is healthy.
- **`.vscode/mcp.json` fails to start with `uv` errors.** The scaffolded
  config for adopted projects invokes the installed `copilot-graph-spec` console
  script directly (no `uv` dependency); only *this* repo's own `.vscode/mcp.json`
  requires `uv` (since it builds `copilot-graph-spec` from source in `copilot_graph_spec/`).

## Editor & client support

The 8 `graph_*` MCP tools are client-agnostic — any MCP-compatible host
(VS Code, Claude Desktop, etc.) can use them once `copilot-graph-spec serve` is
registered. The 5-stage SDD workflow (`.github/agents/*.agent.md` +
`.github/prompts/*.prompt.md`) uses VS Code's Copilot custom-agent format
specifically — other MCP hosts get the graph tools but not that workflow.

## CLI

| Command | Purpose |
| --- | --- |
| `copilot-graph-spec index [ROOT] [--db PATH] [--incremental]` | Build (or incrementally update) the graph database |
| `copilot-graph-spec embed [--db PATH] [--backend NAME] [--model NAME] [--force]` | Compute embeddings for hybrid search |
| `copilot-graph-spec watch [ROOT] [--db PATH] [--interval N]` | Poll for changes; incrementally re-index + re-embed |
| `copilot-graph-spec serve [--root PATH] [--db PATH]` | Run the MCP server over stdio |
| `copilot-graph-spec init [TARGET] [--force]` | Scaffold the SDD workflow + MCP config into an existing project |
| `copilot-graph-spec --version` | Print the installed version |

`index`/`embed`/`watch`/`serve` resolve `ROOT`/`--db` in this order: explicit
flag > nearest `.copilot-graph-spec.toml` (written by `init`, or hand-authored) >
built-in default. See [copilot_graph_spec/src/copilot_graph_spec/config.py](copilot_graph_spec/src/copilot_graph_spec/config.py).

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

- `copilot_graph_spec/src/copilot_graph_spec/indexer` — tree-sitter code parsing + the
  `spec/features/**` markdown parser, both incremental-aware. Adding a
  language means adding a `LanguageConfig` entry to
  [indexer/languages.py](copilot_graph_spec/src/copilot_graph_spec/indexer/languages.py) (a
  code-level extension point today, not a runtime plugin system).
- `copilot_graph_spec/src/copilot_graph_spec/embeddings` — pluggable embedder (`fastembed`
  default, `sentence-transformers` opt-in via the `[torch]` extra).
- `copilot_graph_spec/src/copilot_graph_spec/db` — SQLite schema/connection helpers.
- `copilot_graph_spec/src/copilot_graph_spec/mcp_server` — the 8 `graph_*` tool implementations.
- `copilot_graph_spec/src/copilot_graph_spec/cli` — the `copilot-graph-spec` command line entry point.
- `copilot_graph_spec/src/copilot_graph_spec/config.py` — `.copilot-graph-spec.toml` discovery for
  relocatable `root`/`db` defaults.
- `copilot_graph_spec/src/copilot_graph_spec/init_cmd.py` + `scaffold/` — the bundled
  templates and logic behind `copilot-graph-spec init`.

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

`copilot-graph-spec init` (see Quick Start) drops the same workflow files this repo
uses into any other repo, without vendoring `copilot_graph_spec`'s source: `.vscode/mcp.json`
pointing at the installed console script, `.github/agents`+`prompts`+`instructions`,
`spec/constitution.md`+`templates`, and a `.copilot-graph-spec.toml` so `index`/`embed`/`serve`
work from that repo's own root without extra flags. Run `copilot-graph-spec index . && copilot-graph-spec embed`
afterward, then start a feature with `/specify` as usual.

## Directory Layout

```
.github/
  copilot-instructions.md
  instructions/graph-usage.instructions.md   # always-on: prefer graph queries
  agents/{spec,plan,tasks,implement,analyze}.agent.md
  prompts/{specify,plan,tasks,implement,analyze}.prompt.md
  workflows/{ci,release}.yml
docs/
  USER_GUIDE.md              # full manual: CLI, MCP tools, config, workflow, troubleshooting
spec/
  constitution.md
  templates/{spec,plan,tasks,research}.template.md
  features/<slug>/{spec.md,plan.md,tasks.md,research.md}
copilot_graph_spec/
  pyproject.toml
  .copilot-graph-spec.toml  # this repo's own root/db config (dogfood)
  src/copilot_graph_spec/{indexer,mcp_server,cli,db,embeddings,config.py,init_cmd.py,scaffold}
  tests/
.graph/graph.db            # generated index (gitignored)
.vscode/mcp.json           # registers stdio server (uv run copilot-graph-spec serve)
scripts/                   # index / refresh / validate helpers
LICENSE
CONTRIBUTING.md
```

## Development

```bash
cd copilot_graph_spec
uv run pytest       # full test suite
```

See [CONTRIBUTING.md](CONTRIBUTING.md) for the release process. Licensed
under [MIT](LICENSE).

## Status

v1 implemented (9 phases, see [PLANNING.md](PLANNING.md)) including this
shareability hardening pass — CI, packaging, `.copilot-graph-spec.toml`, and
`copilot-graph-spec init` for adopting the tool into other projects.

 