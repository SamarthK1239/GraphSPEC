"""tree-sitter based parsing -> nodes/edges (Phase 1)."""

from copilot_graph_spec.indexer.core import IndexStats, build_index
from copilot_graph_spec.indexer.incremental import incremental_index
from copilot_graph_spec.indexer.spec_parser import extract_spec_features

__all__ = ["IndexStats", "build_index", "incremental_index", "extract_spec_features"]
