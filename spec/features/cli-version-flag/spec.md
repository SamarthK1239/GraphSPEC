# CLI Version Flag

- **Slug:** `cli-version-flag`
- **Status:** Draft
- **Owner:**

## Summary

Add a `--version` flag to the `graph-mcp` CLI entry point so users can print
the installed `graph-mcp` package version without invoking a subcommand.

## Problem Statement

`graph_mcp/src/graph_mcp/cli.py` defines `main` as a `click.Group` with
`index`, `embed`, and `watch` subcommands, but there is no way to check which
version of `graph-mcp` is installed short of inspecting `pyproject.toml` or
package metadata directly. Users and scripts (e.g. CI, bug reports) need a
quick, standard way to confirm the installed version.

## Goals

- Let users run `graph-mcp --version` to print the installed package version
  and exit, with no subcommand required.
- Source the printed version from installed package metadata (the single
  source of truth already declared in [graph_mcp/pyproject.toml](../../../graph_mcp/pyproject.toml)),
  not a hardcoded/duplicated string, so it can't drift out of sync.

## Non-Goals

- No `-v` short flag alias — only the long `--version` form is required.
- No independent versioning of individual subcommands (`index`, `embed`,
  `watch`); only the top-level CLI/package version is reported.

## Requirements

- REQ-001: Running `graph-mcp --version` prints the installed `graph-mcp`
  package version to stdout and exits with status code 0.
- REQ-002: `--version` is a flag on the top-level `main` group and works
  without supplying any subcommand (e.g. `graph-mcp --version` is valid;
  a subcommand like `index` is not required).

## Open Questions

- Exact printed format (e.g. bare version string like `0.1.0` vs. a
  Click-style `<prog>, version <ver>` line) is left to `plan.md` to decide;
  assumed acceptable either way since no format was specified, as long as the
  version string itself is present and correct.
