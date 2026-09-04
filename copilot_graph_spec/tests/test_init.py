"""Tests for `copilot-graph-spec init` scaffolding (`copilot_graph_spec.init_cmd`)."""

from __future__ import annotations

import json
from pathlib import Path

from copilot_graph_spec.init_cmd import scaffold_project


def test_scaffold_project_creates_expected_tree(tmp_path: Path) -> None:
    report = scaffold_project(tmp_path)
    statuses = dict(report)

    assert statuses[".vscode/mcp.json"] == "created"
    assert statuses[".github/copilot-instructions.md"] == "created"
    assert statuses[".github/instructions/graph-usage.instructions.md"] == "created"
    assert statuses["spec/constitution.md"] == "created"
    assert statuses["spec/templates/spec.template.md"] == "created"
    assert statuses[".copilot-graph-spec.toml"] == "created"
    assert statuses[".gitignore"] in ("created", "appended")
    for agent in ("spec", "plan", "tasks", "analyze", "implement"):
        assert statuses[f".github/agents/{agent}.agent.md"] == "created"

    assert (tmp_path / ".copilot-graph-spec.toml").exists()
    assert not (tmp_path / "copilot-graph-spec.toml.tmpl").exists()
    assert ".graph/" in (tmp_path / ".gitignore").read_text()


def test_scaffold_project_mcp_json_points_at_installed_console_script(tmp_path: Path) -> None:
    scaffold_project(tmp_path)

    config = json.loads((tmp_path / ".vscode" / "mcp.json").read_text())

    assert config["servers"]["copilot-graph-spec"]["command"] == "copilot-graph-spec"
    assert config["servers"]["copilot-graph-spec"]["args"] == ["serve"]


def test_scaffold_project_skips_existing_files_without_force(tmp_path: Path) -> None:
    scaffold_project(tmp_path)
    (tmp_path / "spec" / "constitution.md").write_text("customized by user")

    report = scaffold_project(tmp_path)

    assert dict(report)["spec/constitution.md"] == "skipped"
    assert (tmp_path / "spec" / "constitution.md").read_text() == "customized by user"


def test_scaffold_project_force_overwrites_existing_files(tmp_path: Path) -> None:
    scaffold_project(tmp_path)
    (tmp_path / "spec" / "constitution.md").write_text("customized by user")

    report = scaffold_project(tmp_path, force=True)

    assert dict(report)["spec/constitution.md"] == "created"
    assert (tmp_path / "spec" / "constitution.md").read_text() != "customized by user"


def test_scaffold_project_appends_to_existing_gitignore_without_duplicating(tmp_path: Path) -> None:
    (tmp_path / ".gitignore").write_text("node_modules/\n")

    scaffold_project(tmp_path)
    first_content = (tmp_path / ".gitignore").read_text()
    scaffold_project(tmp_path, force=True)
    second_content = (tmp_path / ".gitignore").read_text()

    assert "node_modules/" in first_content
    assert ".graph/" in first_content
    assert first_content == second_content  # re-running doesn't duplicate the appended line
