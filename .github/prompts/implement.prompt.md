---
description: "Implement the next (or a specific) task from a feature's tasks.md"
agent: implement
argument-hint: "<feature slug> [TASK-<NNN>]"
---

Work through `spec/features/<slug>/tasks.md`: implement the specified task,
or the next unchecked one if none is given. Run its stated verification and
only mark it `[x]` once it actually passes.
