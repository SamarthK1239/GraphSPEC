# Contributing

## Dev setup

```bash
cd graph_mcp
uv pip install -e ".[dev]"   # or: pip install -e ".[dev]"
uv run pytest                # full test suite
```

Optional local checks before pushing:

```bash
uv run graph-mcp index ..    # rebuild .graph/graph.db from the repo root
uv run graph-mcp embed       # populate embeddings for hybrid search
uv build                     # sanity-check packaging (dist/*.whl, dist/*.tar.gz)
```

## CI

[.github/workflows/ci.yml](.github/workflows/ci.yml) runs the test suite on
ubuntu/macos/windows across Python 3.11–3.13 on every push/PR to `main`.

## Release process

1. Bump `version` in [graph_mcp/pyproject.toml](graph_mcp/pyproject.toml).
2. Tag the release: `git tag vX.Y.Z && git push origin vX.Y.Z`.
3. [.github/workflows/release.yml](.github/workflows/release.yml) builds and
   publishes to PyPI via `pypa/gh-action-pypi-publish`. This requires either:
   - PyPI Trusted Publishing configured for this repo (no secret needed —
     uses the `id-token: write` permission already set in the workflow), or
   - a `PYPI_API_TOKEN` repository secret, with the workflow's publish step
     updated to pass it explicitly.

   Both require repo/PyPI admin access to set up once; this is not something
   that can be automated from within the repo itself.

## Adding a language to the indexer

Add a `LanguageConfig` entry to
[graph_mcp/src/graph_mcp/indexer/languages.py](graph_mcp/src/graph_mcp/indexer/languages.py)
mapping tree-sitter node types (function/class/call/import) for the new
language — see the existing Python/JS/TS entries for the field meanings.
This is a code change today, not a runtime plugin system.
