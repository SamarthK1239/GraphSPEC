# Tasks: CLI Version Flag

Ordered by dependency; each task should be independently implementable and
verifiable before moving to the next.

- [x] TASK-001: Add `@click.version_option(package_name="graph-mcp")` to the
  `main` `click.group()` in `graph_mcp/src/graph_mcp/cli.py`, so
  `graph-mcp --version` prints `graph-mcp, version <installed version>` and
  exits 0 without requiring a subcommand. [covers: REQ-001, REQ-002] [implements: PLAN-001]
- [x] TASK-002: Create `graph_mcp/tests/test_cli.py` with a
  `click.testing.CliRunner`-based test invoking `main` with `["--version"]`,
  asserting exit code 0 and that the installed `graph-mcp` version (via
  `importlib.metadata.version("graph-mcp")`) appears in output. [covers: REQ-001, REQ-002] [implements: PLAN-002]

## Verification Per Task

- TASK-001: run `uv run graph-mcp --version` from `graph_mcp/` per plan.md's
  manual check; confirm exit 0 and the printed version matches
  `graph_mcp/pyproject.toml`'s `version`.
- TASK-002: run `uv run pytest graph_mcp/tests/test_cli.py` per plan.md's
  verification section; confirm it passes.
