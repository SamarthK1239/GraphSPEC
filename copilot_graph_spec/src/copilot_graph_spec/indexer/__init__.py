"""tree-sitter based parsing -> nodes/edges (Phase 1)."""

from graph_mcp.indexer.core import IndexStats, build_index
from graph_mcp.indexer.incremental import incremental_index
from graph_mcp.indexer.spec_parser import extract_spec_features

__all__ = ["IndexStats", "build_index", "incremental_index", "extract_spec_features"]
