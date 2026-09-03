#!/usr/bin/env bash
# Build/refresh the .graph/graph.db index from scratch (Phase 1).
set -euo pipefail
cd "$(dirname "$0")/../graph_mcp"
uv run graph-mcp index "$@"
