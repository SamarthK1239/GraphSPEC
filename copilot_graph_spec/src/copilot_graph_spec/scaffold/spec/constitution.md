# GraphSPEC Constitution

> Governs every feature under `spec/features/`. Amend via PR + explicit rationale;
> treat this file as higher-authority than any single spec/plan/tasks doc.

## Purpose

GraphSPEC exists to make agent-driven development context-efficient: agents
should query a graph for pointers and fetch only the exact spans they need,
never whole files, and every requirement should trace forward to the code that
implements it.

## Core Principles

1. **Pointers over bodies.** Any tool or workflow step that can return a
   path + line span + signature instead of file contents, must.
2. **Verify, don't assume.** Claims about behavior (parser output, library
   APIs, query results) must be checked against real execution before being
   relied on — don't guess field names, schemas, or return shapes.
3. **Standalone and dependency-light.** No dependency on Spec Kit or other
   external SDD frameworks; local embeddings/CPU-only by default; heavyweight
   infra (graph DBs, cloud services) is out of scope for v1.
4. **Traceable by construction.** Every requirement, plan item, and task is
   identifiable and linkable (see Traceability IDs below), so coverage gaps
   are a query, not a manual audit.
5. **Small, verifiable steps.** Plans decompose into phases; tasks are small
   enough to implement and verify independently before moving on.

## Traceability IDs

Requirements, plan items, and tasks use stable IDs so the graph indexer
(Phase 6) can parse `spec/features/**` into nodes and edges without ambiguity:

- `spec.md`: `- REQ-<NNN>: <requirement text>`
- `plan.md`: `- PLAN-<NNN>: <plan item text> [derives: REQ-<NNN>, ...]`
- `tasks.md`: `- TASK-<NNN>: <task text> [covers: REQ-<NNN>, ...] [implements: PLAN-<NNN>, ...]`

IDs are numbered per-feature (reset at 001 in each `spec/features/<slug>/`),
never reused, and never renumbered after being referenced elsewhere.

## Workflow

`constitution → specify → plan → tasks → analyze → implement`

This constitution is authored once per project (not regenerated per feature).
The other five stages are automated via `.github/agents/*.agent.md` +
`.github/prompts/*.prompt.md` and always operate on one feature at a time
under `spec/features/<slug>/`.

## Non-Negotiables

- Don't skip `analyze` before `implement` on features with more than a
  handful of requirements.
- Don't mark a task complete without running its stated verification step.
- Don't introduce scope in `plan.md`/`tasks.md` that doesn't trace back to a
  `REQ-<NNN>` in `spec.md` — flag the gap instead.
