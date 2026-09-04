"""Extract file/symbol nodes and contains/imports/calls edges from a single source file.

Scope (Phase 1, vertical slice): function/class/method definitions become symbol
nodes; `contains` edges link file -> top-level defs -> nested defs; `imports`
edges point at unresolved `external:<module>` targets (real import-path
resolution is future work); `calls` edges resolve callees by simple name within
the same file only (cross-file/dynamic calls are skipped rather than guessed).
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from tree_sitter_language_pack import get_parser

from copilot_graph_spec.indexer.languages import LANGUAGES, LanguageConfig
from copilot_graph_spec.indexer.models import EdgeRecord, NodeRecord


def extract_file(relpath: str, source: bytes, language_key: str) -> tuple[list[NodeRecord], list[EdgeRecord]]:
    cfg = LANGUAGES[language_key]
    parser = get_parser(cfg.ts_name)
    tree = parser.parse(source)

    file_id = f"file:{relpath}"
    line_count = source.count(b"\n") + 1
    nodes: list[NodeRecord] = [
        NodeRecord(
            id=file_id,
            type="file",
            path=relpath,
            name=relpath,
            signature=None,
            line_start=1,
            line_end=line_count,
            hash=hashlib.sha256(source).hexdigest(),
            meta=json.dumps({"language": language_key}),
        )
    ]
    edges: list[EdgeRecord] = []
    name_to_symbol: dict[str, str] = {}
    function_nodes: list[tuple[str, Any]] = []

    def walk_defs(node: Any, parent_id: str, qual_prefix: str) -> None:
        for child in node.children:
            if child.type in cfg.class_types or child.type in cfg.function_types:
                is_class = child.type in cfg.class_types
                name_node = child.child_by_field_name(cfg.name_field)
                name = name_node.text.decode("utf-8", errors="replace") if name_node else "<anonymous>"
                qualified = f"{qual_prefix}.{name}" if qual_prefix else name
                body_node = child.child_by_field_name(cfg.body_field)
                sig_end = body_node.start_byte if body_node is not None else child.end_byte
                signature = (
                    source[child.start_byte : sig_end]
                    .decode("utf-8", errors="replace")
                    .strip()
                    .rstrip(":{ ")
                    .strip()
                )
                symbol_id = f"symbol:{relpath}:{qualified}:{child.start_point[0] + 1}"
                nodes.append(
                    NodeRecord(
                        id=symbol_id,
                        type="symbol",
                        path=relpath,
                        name=qualified,
                        signature=signature,
                        line_start=child.start_point[0] + 1,
                        line_end=child.end_point[0] + 1,
                        hash=hashlib.sha256(source[child.start_byte : child.end_byte]).hexdigest(),
                        meta=json.dumps({"language": language_key, "kind": "class" if is_class else "function"}),
                    )
                )
                edges.append(EdgeRecord(parent_id, symbol_id, "contains"))
                name_to_symbol[name] = symbol_id
                if not is_class:
                    function_nodes.append((symbol_id, child))
                if body_node is not None:
                    walk_defs(body_node, symbol_id, qualified)
            elif child.type in cfg.import_types:
                for target in _import_targets(child, cfg.ts_name):
                    edges.append(EdgeRecord(file_id, f"external:{target}", "imports"))
            else:
                walk_defs(child, parent_id, qual_prefix)

    walk_defs(tree.root_node, file_id, "")

    for symbol_id, func_node in function_nodes:
        body_node = func_node.child_by_field_name(cfg.body_field)
        if body_node is not None:
            _collect_calls(body_node, cfg, edges, symbol_id, name_to_symbol)

    return nodes, edges


def _collect_calls(
    node: Any,
    cfg: LanguageConfig,
    edges: list[EdgeRecord],
    enclosing_symbol_id: str,
    name_to_symbol: dict[str, str],
) -> None:
    for child in node.children:
        if child.type in cfg.function_types or child.type in cfg.class_types:
            continue  # nested scope: resolved separately against its own body
        if child.type in cfg.call_types:
            func_field = child.child_by_field_name(cfg.call_function_field)
            callee = _resolve_callee(func_field, cfg) if func_field is not None else None
            target = name_to_symbol.get(callee) if callee else None
            if target is not None:
                edges.append(EdgeRecord(enclosing_symbol_id, target, "calls"))
        _collect_calls(child, cfg, edges, enclosing_symbol_id, name_to_symbol)


def _resolve_callee(node: Any, cfg: LanguageConfig) -> str | None:
    """Return the callee's simple name, or None if it can't be resolved safely.

    Direct calls (`foo()`) resolve by name. Attribute/member calls
    (`obj.method()`) only resolve when the receiver is a "self"-like
    reference (`self`/`cls`/`this`); other receivers are left unresolved
    since the object's type isn't tracked, and guessing risks false
    positives (e.g. `sqlite3.connect()` matching an unrelated local
    `connect()`).
    """
    if node.type in ("identifier", "property_identifier", "type_identifier"):
        return node.text.decode("utf-8", errors="replace")
    if node.type in cfg.attribute_call_types:
        obj = node.child_by_field_name(cfg.attribute_object_field)
        member = node.child_by_field_name(cfg.attribute_member_field)
        if obj is None or member is None:
            return None
        is_self = obj.type in cfg.self_node_types or (
            obj.type == "identifier" and obj.text.decode("utf-8", errors="replace") in cfg.self_identifiers
        )
        if is_self:
            return member.text.decode("utf-8", errors="replace")
    return None



def _import_targets(node: Any, ts_name: str) -> list[str]:
    if ts_name == "python":
        if node.type == "import_statement":
            targets = []
            for c in node.children:
                if c.type == "dotted_name":
                    targets.append(c.text.decode("utf-8", errors="replace"))
                elif c.type == "aliased_import":
                    dn = c.child_by_field_name("name")
                    if dn is not None:
                        targets.append(dn.text.decode("utf-8", errors="replace"))
            return targets
        if node.type == "import_from_statement":
            mod = node.child_by_field_name("module_name")
            return [mod.text.decode("utf-8", errors="replace")] if mod is not None else []
        return []
    # javascript / typescript / tsx
    if node.type == "import_statement":
        src = node.child_by_field_name("source")
        if src is not None:
            return [src.text.decode("utf-8", errors="replace").strip("\"'")]
    return []
