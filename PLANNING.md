# GraphSPEC — Planning & Design History

> Status: v1 implemented (Phases 0–8 complete) • Last updated: 2026-09-03

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

All 8 phases are complete as of this writing.

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
  federation, CI automation, GitHub Issues sync — noted as future work.

## Known Follow-ups

- The `graph-mcp` MCP server must be started once via VS Code's MCP UI in a
  fresh workspace — it isn't auto-connected on first open, so a brand new
  session's chat agents will fall back to normal file tools until it's
  started.
- `spec_parser.py`'s bullet parser joins wrapped continuation lines onto a
  bullet's first line before matching `REQ-`/`PLAN-`/`TASK-` tags — this
  was a real bug found during the Phase 8 E2E run (a wrapped `[derives:
  ...]` tag was silently dropped) and is now covered by a regression test.
