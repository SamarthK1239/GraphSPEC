# Plan: CLI Version Flag

## Context

`graph_mcp/src/graph_mcp/cli.py` defines `main` as a bare `@click.group()`
with no `--version` support. The console-script entry point is declared in
[graph_mcp/pyproject.toml](../../../graph_mcp/pyproject.toml) as
`graph-mcp = "graph_mcp.cli:main"`, with `[project] name = "graph-mcp"` and
`version = "0.1.0"` — this is the single source of truth for the version
string that must be surfaced by `--version`. No CLI tests currently exist
under `graph_mcp/tests/` (no `click.testing.CliRunner` usage found).

## Approach

Add Click's built-in `@click.version_option(package_name="graph-mcp")`
decorator to the `main` group in `cli.py`. Click resolves the version via
`importlib.metadata.version("graph-mcp")` at call time (reading the same
`pyproject.toml`-declared version, since the package is installed
editable/normally), and prints `<prog>, version <ver>` (e.g.
`graph-mcp, version 0.1.0`) to stdout before exiting 0 — satisfying REQ-001
and REQ-002 without hardcoding or duplicating the version string anywhere in
`cli.py`.

Passing `package_name="graph-mcp"` explicitly (rather than relying on
Click's auto-detection from the decorated function's module) avoids any
ambiguity/failure if module-to-distribution-name inference ever breaks,
since `graph_mcp` (module) and `graph-mcp` (distribution name) differ by a
hyphen/underscore.

**Alternatives considered:**
- Hardcoding a version string constant in `cli.py` — rejected: duplicates
  `pyproject.toml`, can drift out of sync (explicitly a non-goal per spec.md
  Goals).
- Reading `pyproject.toml` directly at runtime (e.g. via `tomllib`) — rejected:
  more code than `importlib.metadata`, and breaks for installed (non-editable,
  no source tree present) deployments where `pyproject.toml` isn't shipped.
- Custom `--version` `click.option(is_flag=True, callback=...)` — rejected:
  reinvents `click.version_option()`'s eager-option/exit-early semantics for
  no behavioral gain; less idiomatic Click.

## Plan Items

- PLAN-001: Add `@click.version_option(package_name="graph-mcp")` to the
  `main` group in `graph_mcp/src/graph_mcp/cli.py`, so `graph-mcp --version`
  prints `graph-mcp, version <installed version>` and exits 0 without
  requiring a subcommand. [derives: REQ-001, REQ-002]
- PLAN-002: Add a CLI test (using `click.testing.CliRunner`) invoking
  `main` with `["--version"]` and asserting exit code 0 and that the
  installed `graph-mcp` version string (via `importlib.metadata.version`)
  appears in output. [derives: REQ-001, REQ-002]

## Relevant Files

- `graph_mcp/src/graph_mcp/cli.py` — add the `version_option` decorator to
  the `main` group definition.
- `graph_mcp/tests/test_cli.py` — new file; `CliRunner`-based test(s)
  covering `--version` exit code and printed version string.

## Verification

- `uv run pytest graph_mcp/tests/test_cli.py` passes, covering PLAN-001/
  PLAN-002 (REQ-001, REQ-002).
- Manual check: from `graph_mcp/`, run `uv run graph-mcp --version` and
  confirm it prints `graph-mcp, version 0.1.0` (matching
  `graph_mcp/pyproject.toml`'s `version`) and exits 0, with no subcommand
  supplied.

## Risks

- If `graph-mcp` is imported/run without being installed as a package (e.g.
  running `cli.py` directly via `python cli.py`), `importlib.metadata` may
  fail to resolve the distribution and raise `PackageNotFoundError` —
  mitigation: this only affects an unsupported/unpackaged invocation mode
  the project doesn't otherwise support (the documented entry point is the
  `graph-mcp` console script from an installed package, per
  `graph_mcp/pyproject.toml`'s `[project.scripts]`), so no code change is
  needed to mitigate it.
