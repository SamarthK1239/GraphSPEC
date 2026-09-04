"""Tests for the graph-mcp CLI entry point."""

from __future__ import annotations

from importlib.metadata import version

from click.testing import CliRunner

from graph_mcp.cli import main


def test_version_flag_prints_version_and_exits_zero() -> None:
    runner = CliRunner()
    result = runner.invoke(main, ["--version"])

    assert result.exit_code == 0
    assert version("copilot-graph-spec") in result.output
