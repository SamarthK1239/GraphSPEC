#!/usr/bin/env bash
# Incrementally re-index only changed files (Phase 7).
set -euo pipefail
cd "$(dirname "$0")/../graph_mcp"
uv run graph-mcp index --incremental "$@"
