---
description: "Cross-check a feature's spec/plan/tasks for consistency and coverage gaps"
agent: analyze
argument-hint: "<feature slug>"
---

Cross-check `spec/features/<slug>/{spec.md,plan.md,tasks.md}` for orphaned
requirements, plan items with no implementing task, dangling ID references,
and scope drift. Report findings only — do not edit any file.
