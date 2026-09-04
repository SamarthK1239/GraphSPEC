"""Tests for `.copilot-graph-spec.toml` discovery/precedence (`copilot_graph_spec.config`)."""

from __future__ import annotations

from pathlib import Path

from copilot_graph_spec.config import find_config, load_config, resolve_path


def test_find_config_returns_none_when_absent(tmp_path: Path) -> None:
    nested = tmp_path / "a" / "b"
    nested.mkdir(parents=True)

    assert find_config(nested) is None


def test_find_config_walks_up_to_nearest_ancestor(tmp_path: Path) -> None:
    (tmp_path / ".copilot-graph-spec.toml").write_text("[copilot-graph-spec]\nroot = '.'\n")
    nested = tmp_path / "a" / "b"
    nested.mkdir(parents=True)

    assert find_config(nested) == tmp_path / ".copilot-graph-spec.toml"


def test_load_config_resolves_paths_relative_to_config_file(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / ".copilot-graph-spec.toml").write_text('[copilot-graph-spec]\nroot = ".."\ndb = "../.graph/graph.db"\n')

    config = load_config(repo)

    assert config["root"] == str(tmp_path.resolve())
    assert config["db"] == str((tmp_path / ".graph" / "graph.db").resolve())


def test_load_config_missing_file_returns_empty_dict(tmp_path: Path) -> None:
    assert load_config(tmp_path) == {}


def test_resolve_path_precedence_cli_over_config_over_default(tmp_path: Path) -> None:
    (tmp_path / ".copilot-graph-spec.toml").write_text('[copilot-graph-spec]\nroot = "from-config"\n')

    assert resolve_path("root", "from-cli", "from-default", start=tmp_path) == "from-cli"
    assert resolve_path("root", None, "from-default", start=tmp_path) == str((tmp_path / "from-config").resolve())


def test_resolve_path_falls_back_to_default_without_config(tmp_path: Path) -> None:
    assert resolve_path("root", None, "from-default", start=tmp_path) == "from-default"
