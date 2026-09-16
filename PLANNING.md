# GraphSPEC — Planning & Design History

> Status: v1 implemented (Phases 0–9 complete) • Last updated: 2026-09-03

This document captures the locked design decisions, phased build history, and
verification methodology behind [README.md](README.md). It's a historical
record of *why* things are built the way they are, not day-to-day usage docs.

## Locked Decisions

- **Standalone, custom layout.** Not built on Spec Kit; no migration concern.
  Still uses the required `.github/` Copilot customization locations.
- **Python tooling.** Official Python MCP SDK (stdio transport),
  `tree-sitter` + `tree-sitter-language-pack` for language-agnostic parsing
  (pinned tree-sitter core version), `click` CLI, `pyproject.toml`, run via
  `uv` (pip + venv fallback).
- **Pluggable local embeddings.** Embedder interface with `fastembed` (ONNX,
  CPU-only) as the default backend, and `sentence-transformers` (PyTorch) as
  an opt-in backend shipped under an optional `[torch]` extra so the default
  install stays lightweight. Model is configurable (default
  `BAAI/bge-small-en-v1.5`, ~130 MB) and downloaded from Hugging Face on
  first run. `graph_search` starts **lexical-only** (FTS5) and upgrades to
  **hybrid** (FTS5 + vector similarity fused with RRF) once embeddings land.
- **Unified graph** with node types `file | symbol | spec | requirement |
  plan_item | task` and edges `imports | calls | references | contains |
  derives | implements | covers | depends_on`.
- **Underscore MCP tool names** (`graph_search`, not `graph.search`) — dotted
  names risk rejection by MCP clients that restrict tool names to
  `[a-zA-Z0-9_-]`.

## Implementation Phases

0. **Scaffold + README** — dirs, `.gitignore` (`.graph/`), `pyproject.toml`
   (with `sentence-transformers` as optional `[torch]` extra),
   `.vscode/mcp.json` skeleton.
1. **Graph indexer core** — tree-sitter (`tree-sitter-language-pack`) →
   nodes/edges → SQLite; `nodes_fts` FTS5; `graph-mcp index` CLI; seed
   Python + TS/JS grammars, pluggable for more.
2. **Graph MCP server — vertical slice** — implement all 8 tools on
   **lexical** search; register in `.vscode/mcp.json`. *(depends on 1;
   proves the context-reduction mechanism early)*
3. **Embeddings + hybrid search** — pluggable embedder (fastembed default,
   sentence-transformers opt-in), sqlite-vec table, RRF fusion; upgrades
   `graph_search` to hybrid. *(depends on 1)*
4. **SPEC workflow layer** — `copilot-instructions.md`, constitution +
   spec/plan/tasks templates, 5 custom agents + 5 prompt files.
   *(parallel, independent)*
5. **Wire graph into agents** — always-on `graph-usage.instructions.md` +
   per-agent tool lists enforcing read-span-on-demand. *(depends on 2, 4)*
6. **Unify artifact graph** — parse `spec/features/*` into nodes/edges;
   `graph_trace` + coverage-gap detection; analyze phase consumes it.
   *(depends on 2, 5)*
7. **Incremental indexing** — mtime/content-hash re-index, optional `watch`
   mode, re-embed only changed nodes. *(depends on 1, 3)*
8. **Validation + docs** — pytest, token-budget benchmark, e2e toy feature.
   *(depends on all)*
9. **Shareability hardening** — `LICENSE` (MIT), CI (`ci.yml`: ubuntu/macos/
   windows x Python 3.11-3.13) + release-on-tag (`release.yml`, PyPI),
   `.graph-mcp.toml` config-file discovery decoupling `index`/`embed`/
   `watch`/`serve` from the hardcoded `graph_mcp/`-is-one-level-under-root
   layout, and a `graph-mcp init <target>` command that scaffolds the SDD
   workflow (agents/prompts/instructions/spec templates/mcp.json) into any
   other repo so `graph-mcp` can be adopted as an installed package instead
   of vendored monorepo code. *(depends on all; addresses adoption barriers
   found via a shareability review)*

All 9 phases are complete as of this writing.

## Verification

1. **Unit (pytest):** index a sample repo → assert node/edge counts, symbol
   resolution, embeddings populated. ✅ `graph_mcp/tests/`
2. **MCP protocol:** all tool schemas valid; calls return pointers, not
   bodies. ✅ Validated via a real `mcp.client.stdio` + `ClientSession`
   round-trip against the running server (Node/MCP Inspector wasn't
   available in the dev sandbox this was built in).
3. **Hybrid search:** a semantic query with no keyword overlap still finds
   the right symbol via the vector path. ✅
   `test_hybrid_search_finds_semantic_match_without_keyword_overlap`.
4. **Token benchmark:** graph-path vs. whole-file reads on a sample task. ✅
   `test_token_benchmark.py` — measured **83.7% token reduction** (674 →
   110 estimated tokens) reading a single relevant function out of a ~70
   function file via `graph_search` + `graph_read_span` vs. reading the
   whole file.
5. **E2E:** ran the full spec → plan → tasks → analyze → implement workflow
   on a real toy feature (`spec/features/cli-version-flag/`, adding a
   `--version` flag to the CLI) using the actual custom agents, confirming
   the workflow produces genuinely-verified, traceable code changes end to
   end. Kept as a permanent worked example.
6. **Traceability:** `graph_trace` surfaces an intentionally-missing
   requirement → task coverage gap. ✅ `test_spec_parser.py`.

## Scope

- **Included:** SDD workflow files, unified graph, MCP server, CLI, local
  embeddings/hybrid search, incremental indexing, traceability, benchmarks.
- **Excluded (v1):** heavyweight graph DB (Neo4j/Kùzu), cross-repo/monorepo
  federation, GitHub Issues sync, a runtime language-plugin system (adding a
  language is still a code-level edit to `languages.py`) — noted as future
  work.

## Known Follow-ups

- The `graph-mcp` MCP server must be started once via VS Code's MCP UI in a
  fresh workspace — it isn't auto-connected on first open, so a brand new
  session's chat agents will fall back to normal file tools until it's
  started.
- `spec_parser.py`'s bullet parser joins wrapped continuation lines onto a
  bullet's first line before matching `REQ-`/`PLAN-`/`TASK-` tags — this
  was a real bug found during the Phase 8 E2E run (a wrapped `[derives:
  ...]` tag was silently dropped) and is now covered by a regression test.
- Actually publishing to PyPI (creating the account, adding a
  `PYPI_API_TOKEN`/trusted-publisher secret) is a manual one-time step
  `release.yml` depends on but can't do on its own. The distribution is
  named `copilot-graph-spec` on PyPI (`graph-mcp` and `graph-spec` were
  both already taken); the installed console script/CLI command originally
  remained `graph-mcp` — see Phase 11 below, which renamed it too.

## Phase 11: `graph-mcp` → `copilot-graph-spec` full rename

`graph-mcp` collided in name with Microsoft's own `graph-mcp` MCP server,
causing confusion. Renamed everywhere to `copilot-graph-spec`, matching the
PyPI distribution name:

- Top-level project dir `graph_mcp/` → `copilot_graph_spec/`, and the
  Python package `graph_mcp` → `copilot_graph_spec` (all imports, the
  `[project.scripts]` entry point, `[tool.hatch.build.targets.wheel]`
  `packages` path).
- CLI console script `graph-mcp` → `copilot-graph-spec` (e.g.
  `copilot-graph-spec index .`).
- MCP server registration name (`.vscode/mcp.json`, both this repo's and
  the scaffolded one) and agent tool-grant tags (`graph-mcp/*` →
  `copilot-graph-spec/*` in every `.agent.md`).
- Config file `.graph-mcp.toml` → `.copilot-graph-spec.toml` (including its
  `[graph-mcp]` → `[copilot-graph-spec]` TOML table, the scaffold template
  `graph-mcp.toml.tmpl` → `copilot-graph-spec.toml.tmpl`, and this repo's
  own dogfooded config file).
- Env vars `GRAPH_MCP_EMBED_BACKEND`/`GRAPH_MCP_EMBED_MODEL` →
  `COPILOT_GRAPH_SPEC_EMBED_BACKEND`/`COPILOT_GRAPH_SPEC_EMBED_MODEL`.
- All prose mentions across README, USER_GUIDE, CONTRIBUTING,
  copilot-instructions, and CI/release workflow `working-directory`/
  `packages-dir` paths.

Left untouched intentionally: the `GraphSPEC` project/repo name itself, the
individual `graph_*` MCP tool names (`graph_search`, `graph_read_span`,
etc. — generic enough not to collide with Microsoft's server), and the
historical record above (including `spec/features/cli-version-flag/*.md`,
which still references the old `graph_mcp/` paths as they were at the time
that example was built).

## Phase 12: token-optimization hardening

Audited the 8 `graph_*` tools for remaining token-efficiency gaps beyond the
already-measured 83.7% reduction (Phase 8's benchmark) and closed four:

- **Bounded result sets**: `graph_file_outline`, `graph_neighbors`,
  `graph_impact`, and `graph_trace`'s coverage-gap listing previously had no
  result cap (unlike `graph_search`/`graph_subgraph`, which already clamped
  limits). All four now accept a `limit`/`max_results` param (generous
  defaults, backward compatible) and report `"truncated": true` when a
  caller should narrow its query instead of assuming it saw everything.
- **Field-selection (`fields=`) projection**: every node-returning tool
  (`graph_search`, `graph_file_outline`, `graph_get_symbol`,
  `graph_neighbors`, `graph_impact`, `graph_subgraph`) now accepts an
  optional `fields` list to shrink each result down to just the requested
  keys (e.g. `fields=["id","name"]`) — `None` (default) preserves the
  original full-shape behavior.
- **Populated the previously-dead `doc` field**: `nodes_fts.doc` existed in
  the schema since Phase 1 but was always inserted as `NULL`; `nodes` had no
  `doc` column at all. Added `doc TEXT` to `nodes` (with an `ALTER TABLE`
  migration guard in `connect()` for pre-existing DBs), extract each Python
  symbol's first docstring line in `extractor.py` (JS/TS/TSX intentionally
  out of scope — no reliable docstring node, would need raw-comment
  scanning), and wire it through `write_records`/`_row_to_node`. Lets
  `graph_search`/`graph_get_symbol` answer "what does this do" without a
  follow-up `graph_read_span` call.
- **Graceful `graph_read_span` overflow**: spans over 500 lines used to
  hard-fail with `ValueError`; now clamped to 500 lines and returned as a
  successful partial result with `"truncated": true` and a
  `"next_line_start"` cursor, avoiding a guess-and-retry round trip.

All changes are additive/backward compatible except the read_span overflow
behavior change (error → truncated success), which is a deliberate, scoped
exception — the one existing test asserting the old error was updated to
assert the new truncated shape instead. `test_token_benchmark.py` gained two
new measured cases (`fields=` projection savings on a 30-caller fan-in, and
`doc`-avoids-a-round-trip) alongside the original whole-file-vs-graph-path
benchmark. 57 tests total (was 47).


