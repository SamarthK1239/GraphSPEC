#!/usr/bin/env bash
# Incrementally re-index only changed files (Phase 7).
set -euo pipefail
cd "$(dirname "$0")/../copilot_graph_spec"
uv run copilot-graph-spec index --incremental "$@"
