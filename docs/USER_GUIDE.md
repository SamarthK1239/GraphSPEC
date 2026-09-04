# GraphSPEC User Guide

This is the full manual for GraphSPEC — the README's Quick Start gets you
running in a few commands; this guide covers every CLI command, MCP tool,
configuration option, and workflow stage in depth, plus troubleshooting and
day-to-day usage patterns. See also [PLANNING.md](../PLANNING.md) for design
history and [CONTRIBUTING.md](../CONTRIBUTING.md) for the dev/release process.

## Table of contents

1. [Concepts](#concepts)
2. [Installing](#installing)
3. [The graph database lifecycle](#the-graph-database-lifecycle)
4. [CLI reference](#cli-reference)
5. [Configuration (`.graph-mcp.toml`)](#configuration-graph-mcptoml)
6. [MCP tools reference](#mcp-tools-reference)
7. [Connecting an MCP client](#connecting-an-mcp-client)
8. [The spec-driven workflow](#the-spec-driven-workflow)
9. [Traceability ID conventions](#traceability-id-conventions)
10. [Embeddings and hybrid search](#embeddings-and-hybrid-search)
11. [Incremental indexing and `watch`](#incremental-indexing-and-watch)
12. [Adding a language to the indexer](#adding-a-language-to-the-indexer)
13. [Retrofitting an existing project](#retrofitting-an-existing-project)
14. [Troubleshooting](#troubleshooting)
15. [FAQ](#faq)

## Concepts

GraphSPEC has two halves that share one SQLite database:

- **A code graph.** `graph-mcp index` walks your repo, parses recognized
  source files with tree-sitter, and stores `file`/`symbol` nodes plus
  `imports`/`calls`/`references`/`contains` edges between them.
- **A spec graph.** The same indexing pass also parses
  `spec/features/**/{spec,plan,tasks}.md` into `spec`/`requirement`/
  `plan_item`/`task` nodes, linked by `derives`/`implements`/`covers` edges
  back to the code graph and to each other (see
  [Traceability ID conventions](#traceability-id-conventions)).

Both graphs are queried through the same 8 `graph_*` MCP tools, so an agent
can jump from "which requirement does this function satisfy?" to "who calls
this function?" without leaving the graph.

The core design goal is **context efficiency**: every tool returns pointers
(node id, path, line span, signature) rather than file contents. Only
`graph_read_span` reads actual source text, and only for the exact range you
ask for. This is what keeps token usage flat as a codebase grows, compared to
an agent that reads whole files to find what it needs.

## Installing

```bash
pip install copilot-graph-spec        # or: uv tool install copilot-graph-spec
```

This installs the `graph-mcp` console script. Verify with:

```bash
graph-mcp --version
graph-mcp --help
```

Requires Python 3.11+. If you're developing GraphSPEC itself (not just using
it), see the "Developing GraphSPEC itself" section in the
[README](../README.md) instead — you'll work from an editable install in
`graph_mcp/`.

## The graph database lifecycle

A minimal end-to-end setup for any project:

```bash
graph-mcp init               # 1. scaffold workflow files + .graph-mcp.toml
graph-mcp index .            # 2. build .graph/graph.db
graph-mcp embed               # 3. populate embeddings for hybrid search
graph-mcp serve                # 4. run the MCP server (usually started by your editor, not by hand)
```

After the initial build, keep the graph fresh either by:

- re-running `graph-mcp index . --incremental` after changes, or
- running `graph-mcp watch` in the background to do this automatically.

The database (`.graph/graph.db` by default) is a plain SQLite file. It's
disposable and gitignored — delete it and re-run `index` at any time to
rebuild from scratch.

## CLI reference

### `graph-mcp index [ROOT] [--db PATH] [--incremental]`

Walks `ROOT` (default: current directory, or `.graph-mcp.toml`'s `root`),
parses every recognized source file, and (re)builds the graph database at
`--db` (default: `.graph/graph.db`, or `.graph-mcp.toml`'s `db`).

- Without `--incremental`: full rebuild — drops and recreates all nodes/edges
  derived from source files.
- With `--incremental`: only re-parses files whose content hash changed since
  the last index (see [Incremental indexing](#incremental-indexing-and-watch)),
  and removes nodes for files that were deleted.

Prints a summary line: files indexed/skipped/removed, and resulting node/edge
counts.

### `graph-mcp embed [--db PATH] [--backend NAME] [--model NAME] [--force]`

Computes vector embeddings for graph nodes and stores them in the `vec_nodes`
sqlite-vec table, enabling semantic (not just lexical) search via
`graph_search`.

- `--backend`: `fastembed` (default, CPU-only, no extra install) or
  `sentence-transformers` (requires the `[torch]` extra: `pip install
  "copilot-graph-spec[torch]"`).
- `--model`: override the backend's default embedding model name.
- `--force`: recompute embeddings for every node, not just ones missing one
  (use this after switching `--backend`/`--model`, since old and new vectors
  aren't comparable).

Without running `embed` at all, `graph_search` still works — it just falls
back to FTS5 lexical-only search.

### `graph-mcp watch [ROOT] [--db PATH] [--interval N]`

Polls `ROOT` every `N` seconds (default `2.0`) and, on any change, runs an
incremental re-index followed by an incremental re-embed (only if the
database already has an embeddings table, i.e. `embed` was run at least
once). Runs until interrupted with Ctrl+C. Useful for keeping a long-lived
editor session's graph continuously up to date without remembering to
re-run `index`/`embed` by hand.

### `graph-mcp serve [--root PATH] [--db PATH]`

Runs the MCP server over stdio, exposing the 8 `graph_*` tools to any
connected MCP client. `--root` is the directory `graph_read_span` resolves
file paths against (default: `.graph-mcp.toml`'s `root`, else the parent of
`graph_mcp/`); `--db` is the database built by `index` (default:
`.graph-mcp.toml`'s `db`, else `../.graph/graph.db`).

You normally don't run this by hand — your editor/MCP client launches it
according to its MCP server configuration (e.g. `.vscode/mcp.json`). See
[Connecting an MCP client](#connecting-an-mcp-client).

### `graph-mcp init [TARGET] [--force]`

Scaffolds the GraphSPEC spec-driven workflow into `TARGET` (default: current
directory): `.vscode/mcp.json`, `.github/{agents,prompts,instructions,
copilot-instructions.md}`, `spec/{constitution.md,templates}`, and a
`.graph-mcp.toml` (see [Configuration](#configuration-graph-mcptoml)). Also
appends a `.graph/` entry to `TARGET/.gitignore` (creating it if absent,
appending idempotently if present).

Existing files are left untouched by default; pass `--force` to overwrite
them. Prints a per-file report (`created` / `skipped` / `appended` /
`unchanged`) so you can see exactly what changed.

### `graph-mcp --version`

Prints the installed package version and exits.

## Configuration (`.graph-mcp.toml`)

Optional TOML file that gives `index`/`embed`/`watch`/`serve` a project's
own `root`/`db` defaults, so those commands work from any working directory
without repeating `--db`/`ROOT` flags every time. Written automatically by
`graph-mcp init`; you can also hand-author or edit one.

```toml
[graph-mcp]
root = "."                  # resolved relative to this file's own directory
db = ".graph/graph.db"
```

**Discovery:** each command walks upward from the current working directory
looking for the nearest `.graph-mcp.toml` (like `.git`/`.editorconfig`
discovery). `root`/`db` values in the file are resolved relative to the
config file's own directory, not the cwd.

**Precedence** (highest to lowest):

1. An explicit `--db`/`ROOT` CLI argument.
2. The value from the nearest `.graph-mcp.toml`.
3. The command's hardcoded built-in default (e.g. `.graph/graph.db`).

This repo dogfoods it via [graph_mcp/.graph-mcp.toml](../graph_mcp/.graph-mcp.toml)
(`root = ".."`, `db = "../.graph/graph.db"`), since `serve` is normally run
with `graph_mcp/` as the working directory but the repo root one level up.

## MCP tools reference

All 8 tools are registered by `graph_mcp/src/graph_mcp/mcp_server/server.py`
and share a single SQLite connection pattern (a short-lived connection per
call — MCP dispatches sync tools onto worker threads, so connections aren't
shared across calls).

| Tool | Signature | Returns |
| --- | --- | --- |
| `graph_search` | `(query: str, limit: int = 20)` | Hybrid lexical+semantic ranked node list (falls back to lexical-only without embeddings) |
| `graph_file_outline` | `(path: str)` | List of symbols (name, signature, line span) declared in `path`, no bodies |
| `graph_get_symbol` | `(node_id: str)` | Signature/location/doc metadata for one node, no body |
| `graph_neighbors` | `(node_id: str, direction: str = "both", edge_types: list[str] \| None = None)` | Nodes connected to `node_id`; `direction` is `in`\|`out`\|`both` |
| `graph_impact` | `(node_id: str, max_depth: int = 2)` | Blast radius — nodes that transitively depend on/call/import `node_id` |
| `graph_subgraph` | `(seed_ids: list[str], max_nodes: int = 50, max_depth: int = 2)` | Focused, token-budgeted slice of the graph around the seed nodes |
| `graph_read_span` | `(path: str, line_start: int, line_end: int)` | Exact source text for a line range (max 500 lines per call) |
| `graph_trace` | `(node_id: str \| None = None)` | Trace neighbors for `node_id`, or (if omitted) a list of coverage gaps across all requirements/plan items |

Notes:

- Every tool returns `{"error": "..."}` on failure (bad node id, SQLite
  error, etc.) instead of raising, so a client always gets a well-formed
  response.
- `graph_search` lazily loads the embedding model only if the database
  actually has a populated `vec_nodes` table — a lexical-only index never
  pays that startup cost.
- `graph_trace` coverage-gap mode only inspects `requirement`/`plan_item`
  nodes (never `task`, since tasks are always edge sources — e.g. `covers`,
  `implements` — never targets).
- `graph_read_span` paths are resolved relative to the server's `--root`
  (or its configured default), not the caller's cwd.

## Connecting an MCP client

Any MCP-compatible host that can launch a stdio server works. The
scaffolded config (written by `graph-mcp init`) is `.vscode/mcp.json`:

```json
{
  "servers": {
    "graph-mcp": {
      "type": "stdio",
      "command": "graph-mcp",
      "args": ["serve"]
    }
  }
}
```

For VS Code: open the MCP view (Command Palette → "MCP: List Servers") and
start `graph-mcp` — it isn't auto-started on first workspace open. Once
started, the 8 `graph_*` tools become available to Copilot Chat agents in
that workspace. For other MCP hosts (Claude Desktop, etc.), point their MCP
server configuration at the same `command`/`args` (adjust for that host's
config format) — the tools themselves are client-agnostic; only the SDD
agent/prompt files under `.github/` are VS Code Copilot-specific.

## The spec-driven workflow

GraphSPEC's SDD workflow has six stages:

```
constitution → specify → plan → tasks → analyze → implement
```

- **constitution** — hand-authored once per project at `spec/constitution.md`
  (copied in by `graph-mcp init`, or edit it directly). States non-negotiable
  principles and the traceability ID format; every other stage treats it as
  higher-authority than any single feature's spec/plan/tasks.
- **specify** (`/specify` prompt, `spec` agent) — writes `spec.md` for a new
  feature under `spec/features/<slug>/`: goals, non-goals, and numbered
  `REQ-<NNN>` requirements.
- **plan** (`plan` agent) — writes `plan.md`: architecture/phases/file-level
  design, as numbered `PLAN-<NNN>` items that each `[derives: REQ-<NNN>, ...]`.
- **tasks** (`tasks` agent) — writes `tasks.md`: an ordered, checkable task
  list, each `TASK-<NNN>` tagged with `[covers: REQ-<NNN>,...] [implements:
  PLAN-<NNN>,...]`.
- **analyze** (`analyze` agent) — cross-checks spec/plan/tasks for
  consistency and coverage gaps (using `graph_trace`) before implementation
  starts; re-run after any of the three docs change.
- **implement** (`implement` agent) — the only stage with `execute`
  permissions; works through `tasks.md` one task at a time, verifying each
  before moving to the next.

Each of the five automated stages is a VS Code custom agent
(`.github/agents/*.agent.md`) plus a matching prompt
(`.github/prompts/*.prompt.md`), all granted the `graph-mcp` MCP tools plus
`read`/`search` (and `execute` for `implement` only). Invoke them via their
prompt (e.g. `/specify`) or by asking for the agent by name.

See [spec/features/cli-version-flag/](../spec/features/cli-version-flag/)
for a complete worked example that went through every stage end to end.

## Traceability ID conventions

IDs are numbered per-feature starting at `001`, are never reused, and are
never renumbered after being referenced elsewhere (per
[spec/constitution.md](../spec/constitution.md)):

```markdown
# spec.md
- REQ-001: <requirement text>

# plan.md
- PLAN-001: <plan item text> [derives: REQ-001]

# tasks.md
- [ ] TASK-001: <task text> [covers: REQ-001] [implements: PLAN-001]
```

The indexer's markdown parser
([indexer/spec_parser.py](../graph_mcp/src/graph_mcp/indexer/spec_parser.py))
turns these into `spec`/`requirement`/`plan_item`/`task` nodes and
`derives`/`implements`/`covers`/`contains` edges. Bullets may wrap across
multiple physical (indented) lines — the parser joins continuation lines
before matching, so multi-line requirement/task text is still parsed
correctly.

`graph_trace` (with no `node_id`) walks this graph looking for
`requirement`/`plan_item` nodes with no incoming coverage edge — i.e.
requirements nobody's plan derives from, or plan items no task implements.
Run it after `analyze` or any manual spec edit to catch drift early.

## Embeddings and hybrid search

`graph_search` starts as pure FTS5 lexical search. Running `graph-mcp embed`
populates a `vec_nodes` sqlite-vec table; once populated, `graph_search`
fuses lexical and vector rankings via **reciprocal-rank fusion (RRF)** for
better recall on paraphrased/semantic queries (e.g. "code that handles user
login" matching a symbol named `authenticate`).

Two embedding backends ([graph_mcp/src/graph_mcp/embeddings/](../graph_mcp/src/graph_mcp/embeddings/)):

- **`fastembed`** (default) — ONNX-based, CPU-only, no extra dependencies
  beyond the base install.
- **`sentence-transformers`** — PyTorch-based; requires the `[torch]` extra
  (`pip install "copilot-graph-spec[torch]"`).

`embed` defaults to `only_missing=True` (skip nodes that already have a
vector); pass `--force` to recompute everything, which you should do after
switching backend or model (vectors from different models aren't
comparable/mixable).

## Incremental indexing and `watch`

`graph-mcp index --incremental` uses a two-tier freshness check
([indexer/incremental.py](../graph_mcp/src/graph_mcp/indexer/incremental.py)):

1. **mtime fast-path** — if a file's modification time matches the last
   indexed run, skip it without reading the file at all.
2. **content-hash authoritative check** — if mtime differs, hash the
   content; only re-parse if the hash actually changed (catches touches
   that don't change content, and cases where mtime granularity/clock skew
   would otherwise cause false rebuilds).

Deleted files are detected and their nodes/edges removed. `graph-mcp watch`
wraps this in a polling loop (default 2s interval) and additionally
re-embeds any newly added nodes if the database already has an embeddings
table — it's the closest thing to "always up to date" without a filesystem
watcher dependency.

## Adding a language to the indexer

Language support is a code-level extension point today (not a runtime
plugin system): add a `LanguageConfig` entry to
[indexer/languages.py](../graph_mcp/src/graph_mcp/indexer/languages.py)
mapping tree-sitter node types (function/class/call/import) for the new
language, following the existing Python/JavaScript/TypeScript/TSX entries.
Then rebuild the index (`graph-mcp index --incremental` picks up newly
recognized file extensions on the next full or incremental run).

## Retrofitting an existing project

`graph-mcp init` (see [Quick Start](../README.md#quick-start)) is the
supported way to add GraphSPEC to a project that doesn't already have it,
without vendoring the `graph_mcp` source tree:

```bash
cd /path/to/existing-project
graph-mcp init
graph-mcp index .
graph-mcp embed
```

This drops in `.vscode/mcp.json` (pointing at the installed `graph-mcp`
console script directly — no `uv`, no vendored subfolder), `.github/{agents,
prompts,instructions}`, `spec/{constitution.md,templates}`, and
`.graph-mcp.toml`. Start a first feature with `/specify` as usual once the
graph is built.

## Troubleshooting

- **MCP tools aren't showing up in chat.** The server is registered but not
  auto-started on first workspace open — open your editor's MCP view
  (VS Code: Command Palette → "MCP: List Servers") and start `graph-mcp`
  manually. Re-running `graph-mcp serve` by hand should succeed with no
  error if the install is healthy; if it doesn't, that's the real bug to
  chase (missing dependency, bad `--db`/`--root` path, etc.).
- **`.vscode/mcp.json` fails to start with `uv` errors.** The scaffolded
  config for adopted projects invokes the installed `graph-mcp` console
  script directly; only the GraphSPEC repo's own `.vscode/mcp.json` needs
  `uv` (it builds `graph-mcp` from source under `graph_mcp/`).
- **`graph_search` returns nothing useful / no semantic matches.** Run
  `graph-mcp embed` at least once; without it, `graph_search` is FTS5
  lexical-only (exact/stemmed keyword matches, no paraphrase matching).
- **Tool calls return `{"error": "no such node: ..."}`.** The `node_id` is
  stale or wrong — re-run `graph_search`/`graph_file_outline` to get current
  ids; ids can shift after a full (non-incremental) reindex.
- **Index/embed pick up the wrong root or database.** Check for a stray
  `.graph-mcp.toml` above your cwd (discovery walks upward through parent
  directories) — an unrelated ancestor project's config can shadow the one
  you expect. Pass explicit `--db`/`ROOT` to bypass it if needed.
- **`graph_read_span` errors with a path/range issue.** Paths are resolved
  against the server's `--root` (see [serve](#graph-mcp-serve---root-path---db-path)),
  not your shell's cwd; ranges are capped at 500 lines per call.
- **Stale results after editing files outside the workflow.** Only
  `graph-mcp index`/`--incremental`/`watch` update the database — nothing
  watches the filesystem implicitly unless `watch` is actually running.

## FAQ

**Does GraphSPEC require an internet connection or an API key?**
No — indexing, the default `fastembed` embedding backend, and the MCP
server all run locally/offline. The workflow is MCP-client-agnostic; any
model access needed by your chosen agent/editor is between you and that
client, not GraphSPEC.

**Is the SDD workflow (`spec`/`plan`/`tasks`/`analyze`/`implement`) required
to use the graph tools?**
No — the 8 `graph_*` tools work standalone against any codebase once
indexed, whether or not you use `spec/features/**`. The SDD workflow is an
optional layer on top that also gets indexed (as `spec`/`requirement`/
`plan_item`/`task` nodes) so it can be queried the same way.

**Can I use this with an MCP client other than VS Code?**
Yes for the graph tools (any MCP-stdio-capable host); the `.github/agents`+
`.github/prompts` custom-agent files are VS Code Copilot-specific and won't
be picked up by other hosts.

**Where does the database live, and should I commit it?**
`.graph/graph.db` by default (or wherever `.graph-mcp.toml`/`--db` points).
It's generated, disposable, and gitignored by default (`graph-mcp init`
appends this for you) — don't commit it; rebuild with `graph-mcp index`.
