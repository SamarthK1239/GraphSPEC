#!/usr/bin/env bash
# Validate the graph MCP server against the MCP Inspector schema checks (Phase 2/8).
set -euo pipefail
cd "$(dirname "$0")/../graph_mcp"
uv run pytest
