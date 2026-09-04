#!/usr/bin/env bash
# Build/refresh the .graph/graph.db index from scratch (Phase 1).
set -euo pipefail
cd "$(dirname "$0")/../copilot_graph_spec"
uv run copilot-graph-spec index "$@"
