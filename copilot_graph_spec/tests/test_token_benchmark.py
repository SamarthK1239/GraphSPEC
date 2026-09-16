"""Phase 8: token-budget benchmark -- graph-path (search + read_span) vs.
naive whole-file reads for a realistic "find and understand a symbol" task.

Uses a simple chars/4 token-estimate proxy (no tokenizer dependency, and good
enough for a relative comparison between the two approaches).
"""

from __future__ import annotations

import json
from pathlib import Path

from copilot_graph_spec.db import connect
from copilot_graph_spec.indexer.core import build_index
from copilot_graph_spec.mcp_server import db_queries
from copilot_graph_spec.mcp_server.read_span import read_span


def _estimate_tokens(text: str) -> int:
    return max(1, len(text) // 4)


SAMPLE_MODULE = '''"""A module with many functions, only one of which is relevant to our task."""


def unrelated_one():
    """Docstring padding to make this file large and realistic."""
    return 1


def unrelated_two():
    return 2


def unrelated_three():
    return 3


def compute_widget_price(base_price, discount_pct):
    """The function we actually need to find and understand."""
    return base_price * (1 - discount_pct / 100)


def unrelated_four():
    return 4


def unrelated_five():
    return 5
'''


def test_graph_path_uses_far_fewer_tokens_than_reading_whole_file(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    # Pad with enough unrelated functions that "read the whole file" has a
    # realistic cost relative to the one function we actually need.
    padding = "\n\n".join(f"def padding_fn_{i}():\n    return {i}\n" for i in range(60))
    module_path = repo / "pricing.py"
    module_path.write_text(SAMPLE_MODULE + "\n\n" + padding)

    db_path = tmp_path / "graph.db"
    build_index(repo, db_path)

    # --- naive: read the whole file to find/understand the function ---
    naive_tokens = _estimate_tokens(module_path.read_text())

    # --- graph-path: search, then read only the exact matching span ---
    conn = connect(db_path)
    search_results = db_queries.search(conn, "compute_widget_price")
    assert search_results, "expected to find compute_widget_price via graph_search"
    target = search_results[0]
    assert target["name"] == "compute_widget_price"

    span_text = read_span(repo, target["path"], target["line_start"], target["line_end"])["text"]
    graph_path_tokens = _estimate_tokens(json.dumps(search_results)) + _estimate_tokens(span_text)

    reduction_pct = 100 * (1 - graph_path_tokens / naive_tokens)
    assert graph_path_tokens < naive_tokens, (
        f"graph-path ({graph_path_tokens} tokens) should be cheaper than naive whole-file "
        f"reads ({naive_tokens} tokens); got {reduction_pct:.0f}% reduction"
    )
    # A real reduction should be substantial for a file this size, not marginal.
    assert reduction_pct > 70, f"expected a large token reduction, got only {reduction_pct:.0f}%"


def test_compact_fields_mode_shrinks_multi_result_payloads(tmp_path: Path) -> None:
    """graph_neighbors with fields=[...] vs. the full default node shape."""
    repo = tmp_path / "repo"
    repo.mkdir()
    # A hub function called by many others -- realistic "who calls this" query.
    callers = "\n\n".join(f"def caller_{i}():\n    return hub()\n" for i in range(30))
    module_path = repo / "hub.py"
    module_path.write_text("def hub():\n    return 1\n\n\n" + callers)

    db_path = tmp_path / "graph.db"
    build_index(repo, db_path)

    conn = connect(db_path)
    hub_id = next(n["id"] for n in db_queries.search(conn, "hub") if n["name"] == "hub")

    full = db_queries.neighbors(conn, hub_id, direction="in")
    compact = db_queries.project_list(full["incoming"], ["id", "name"])

    full_tokens = _estimate_tokens(json.dumps(full["incoming"]))
    compact_tokens = _estimate_tokens(json.dumps(compact))

    reduction_pct = 100 * (1 - compact_tokens / full_tokens)
    assert compact_tokens < full_tokens
    # Dropping signature/meta/line spans across 30 results should be a large win.
    assert reduction_pct > 30, f"expected a meaningful reduction, got only {reduction_pct:.0f}%"


def test_doc_field_avoids_a_read_span_round_trip(tmp_path: Path) -> None:
    """With a populated `doc`, graph_search alone can answer "what does this do" --
    no follow-up graph_read_span call needed, saving that call's entire token cost."""
    repo = tmp_path / "repo"
    repo.mkdir()
    module_path = repo / "pricing.py"
    module_path.write_text(SAMPLE_MODULE)

    db_path = tmp_path / "graph.db"
    build_index(repo, db_path)

    conn = connect(db_path)
    search_results = db_queries.search(conn, "compute_widget_price")
    target = search_results[0]
    assert target["doc"] == "The function we actually need to find and understand."

    search_only_tokens = _estimate_tokens(json.dumps(search_results))

    span_text = read_span(repo, target["path"], target["line_start"], target["line_end"])["text"]
    search_plus_span_tokens = search_only_tokens + _estimate_tokens(span_text)

    assert search_only_tokens < search_plus_span_tokens
