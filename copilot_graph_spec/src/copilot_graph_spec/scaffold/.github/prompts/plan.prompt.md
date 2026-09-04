---
description: "Create or update a feature's plan.md from its approved spec.md"
agent: plan
argument-hint: "<feature slug>"
---

Read `spec/features/<slug>/spec.md` and produce `plan.md` using
[spec/templates/plan.template.md](../../spec/templates/plan.template.md).
Every `PLAN-<NNN>` item must `derive` from a `REQ-<NNN>` already present in
`spec.md`; flag any requirement that plan.md can't address as-is.
