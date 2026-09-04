"""Node/edge record dataclasses shared between the extractor and the DB writer."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class NodeRecord:
    id: str
    type: str  # file | symbol | spec | requirement | plan_item | task
    path: str | None
    name: str | None
    signature: str | None
    line_start: int | None
    line_end: int | None
    hash: str | None
    meta: str  # JSON string


@dataclass
class EdgeRecord:
    src: str
    dst: str
    type: str  # imports | calls | references | contains | derives | implements | covers | depends_on
