"""Per-language tree-sitter node-type mappings, keyed by tree-sitter-language-pack name."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import PurePath


@dataclass(frozen=True)
class LanguageConfig:
    ts_name: str
    extensions: tuple[str, ...]
    function_types: tuple[str, ...]
    class_types: tuple[str, ...]
    call_types: tuple[str, ...] = ("call",)
    import_types: tuple[str, ...] = ()
    name_field: str = "name"
    body_field: str = "body"
    call_function_field: str = "function"
    # Attribute/member calls (obj.method()): only resolved when the receiver is
    # a "self" reference, to avoid false-positive matches against unrelated
    # same-named functions (e.g. `sqlite3.connect()` vs. a local `connect()`).
    attribute_call_types: tuple[str, ...] = ()
    attribute_object_field: str = "object"
    attribute_member_field: str = "attribute"
    self_identifiers: tuple[str, ...] = ()
    self_node_types: tuple[str, ...] = ()


LANGUAGES: dict[str, LanguageConfig] = {
    "python": LanguageConfig(
        ts_name="python",
        extensions=(".py",),
        function_types=("function_definition",),
        class_types=("class_definition",),
        call_types=("call",),
        import_types=("import_statement", "import_from_statement"),
        attribute_call_types=("attribute",),
        attribute_member_field="attribute",
        self_identifiers=("self", "cls"),
    ),
    "javascript": LanguageConfig(
        ts_name="javascript",
        extensions=(".js", ".jsx", ".mjs", ".cjs"),
        function_types=("function_declaration", "method_definition"),
        class_types=("class_declaration",),
        call_types=("call_expression",),
        import_types=("import_statement",),
        attribute_call_types=("member_expression",),
        attribute_member_field="property",
        self_node_types=("this",),
    ),
    "typescript": LanguageConfig(
        ts_name="typescript",
        extensions=(".ts",),
        function_types=("function_declaration", "method_definition"),
        class_types=("class_declaration",),
        call_types=("call_expression",),
        import_types=("import_statement",),
        attribute_call_types=("member_expression",),
        attribute_member_field="property",
        self_node_types=("this",),
    ),
    "tsx": LanguageConfig(
        ts_name="tsx",
        extensions=(".tsx",),
        function_types=("function_declaration", "method_definition"),
        class_types=("class_declaration",),
        call_types=("call_expression",),
        import_types=("import_statement",),
        attribute_call_types=("member_expression",),
        attribute_member_field="property",
        self_node_types=("this",),
    ),
}

_EXTENSION_TO_LANGUAGE: dict[str, str] = {
    ext: lang_key for lang_key, cfg in LANGUAGES.items() for ext in cfg.extensions
}


def detect_language(path: str) -> str | None:
    """Return the LANGUAGES key for a file path's extension, or None if unsupported."""
    return _EXTENSION_TO_LANGUAGE.get(PurePath(path).suffix)
