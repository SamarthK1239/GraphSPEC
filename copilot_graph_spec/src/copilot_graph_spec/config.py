"""Optional `.copilot-graph-spec.toml` discovery, giving CLI defaults for root/db
that work outside the copilot_graph_spec/-vendored monorepo layout (see
`copilot-graph-spec init`).
"""

from __future__ import annotations

import tomllib
from pathlib import Path

CONFIG_FILENAME = ".copilot-graph-spec.toml"


def find_config(start: Path | None = None) -> Path | None:
    """Walk upward from `start` (default: cwd) looking for a `.copilot-graph-spec.toml`."""
    current = (start or Path.cwd()).resolve()
    for directory in (current, *current.parents):
        candidate = directory / CONFIG_FILENAME
        if candidate.is_file():
            return candidate
    return None


def load_config(start: Path | None = None) -> dict[str, str]:
    """Load `root`/`db` from the nearest `.copilot-graph-spec.toml`, resolved
    relative to that file's own directory. Returns {} if no config file is found.
    """
    config_path = find_config(start)
    if config_path is None:
        return {}
    with config_path.open("rb") as fh:
        table = tomllib.load(fh).get("copilot-graph-spec", {})
    return {
        key: str((config_path.parent / table[key]).resolve())
        for key in ("root", "db")
        if key in table
    }


def resolve_path(key: str, cli_value: str | None, default: str, *, start: Path | None = None) -> str:
    """Precedence: explicit CLI value > `.copilot-graph-spec.toml` > the command's hardcoded default."""
    if cli_value is not None:
        return cli_value
    return load_config(start).get(key, default)
