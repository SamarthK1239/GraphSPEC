---
description: "Create or update a feature's tasks.md from its approved plan.md"
agent: tasks
argument-hint: "<feature slug>"
---

Read `spec/features/<slug>/plan.md` and produce `tasks.md` using
[spec/templates/tasks.template.md](../../spec/templates/tasks.template.md).
Order tasks by real dependency and tag each `TASK-<NNN>` with the
`REQ-<NNN>`/`PLAN-<NNN>` IDs it covers/implements.
