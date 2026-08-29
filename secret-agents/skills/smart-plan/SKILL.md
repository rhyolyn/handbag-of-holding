---
name: smart-plan
description: Use when creating or revising an implementation plan that may span agents or sessions and needs explicit model routing, context-efficient batches, copy/paste handoffs, or durable progress tracking.
---

# Smart Plan

Produce an execution plan another agent can resume without conversation history. Route each task to the least expensive capable model, batch work by shared context, and make progress durable in the plan itself.

## Workflow

### 1. Establish the planning boundary

Record the goal, architecture, constraints, repository root, source-of-truth documents, and file/responsibility map. Inspect enough real repository context to name concrete paths, interfaces, commands, and expected results. Label unresolved facts; do not invent them.

### 2. Route every task through centralized profiles

1. Load `<agent-root>/model-routing.json` and run `update-model-routing`'s checker (`python skills/update-model-routing/scripts/check_staleness.py --reference model-routing.json`).
2. If the checker reports `STALE`, invoke `update-model-routing` before finalizing the plan; never silently use stale routing.
3. Assign the weakest adequate named profile to every task and batch. Put exact IDs only in the centralized reference, never in task text or copy/paste handoffs.
4. Before actual dispatch, verify the profile's IDs against the harness-visible allowlist. Record any same-provider, same-or-higher-capability substitution without rewriting task text.
5. Preserve the profile meanings: `high-risk` for destructive/cross-platform/rollback/security work, `balanced` for ambiguous integration work, `routine` for bounded established patterns, and `economy` for mechanical prose or inventory work.

### 3. Form context-cohesive batches

Group consecutive tasks only when one agent benefits materially from retaining the same files, contracts, or verification state. Split batches at independent work, high-risk review boundaries, or a clean handoff point. Do not batch merely to assign “Agent A” and “Agent B.”

At each batch heading include:

- a batch completion checkbox;
- the named routing profile matching the highest capability required by any task in the batch;
- one complete copy/paste handoff prompt before the tasks.

### 4. Write a self-contained batch handoff

Use this contract:

```text
Implement Batch <N>: <name> from <absolute plan path>.

Model routing: use the <profile> profile from model-routing.json. Verify harness availability before dispatch and record any allowed substitution.
Repository root / working directory: <absolute path>

Read only this context before starting:
1. <absolute path plus exact section, symbol, or bounded directory>
2. ...

Starting point: <exact task and step, required branch/commit/tree state, and completed dependency>.

Execution rules:
- <scope, test, safety, staging, and commit rules needed for this batch>
- Check off each step immediately after its verification succeeds; commit plan checkbox updates with the work.
- Preserve unrelated changes and report exact command outcomes.
- Do not read or implement later batches.

Stopping point: stop after <exact final task/step, verification, checkbox, commit, and tree-state conditions>. Report <required evidence>. Do not begin <next task/batch>.
```

The prompt must remain sufficient when pasted into a fresh session with all earlier conversation removed. Prefer exact files and sections over broad directories. Include every dependency the recipient needs, and nothing merely informative.

### 5. Make task progress durable

For every task include:

- `- [ ] Task <N> complete`
- the named routing profile;
- files to create/modify/test;
- consumed and produced interfaces;
- small numbered or checkbox steps with exact commands and expected RED/GREEN or validation outcomes;
- scoped staging/commit instructions when commits are part of the workflow.

Require executors to check a step only after its evidence succeeds, and to commit plan checkbox changes with the corresponding work. End with a completion checklist covering deliverables, verification, external evidence, and clean working state.

## Final Audit

Before delivering the plan, verify:

- every task and batch names one routing profile from model-routing.json, and the checker reports CURRENT before finalizing;
- every batch is justified by shared context and has its own routing and copy/paste handoff;
- every handoff names absolute context paths and exact starting and stopping points;
- a fresh agent can act without reading earlier batches or conversation;
- all tasks, steps, batches, and final gates have durable checkboxes;
- commands, expected outcomes, and staging scopes are concrete;
- placeholders, stale model IDs, vague directories, and hidden prerequisites are absent.

## Common Failure Modes

| Failure | Correction |
|---|---|
| “Use a Sonnet-tier model” | Name one profile (high-risk/balanced/routine/economy); exact IDs live only in model-routing.json. |
| Tasks grouped under Agent A/Agent B | Re-batch around shared files, contracts, and verification state. |
| One generic handoff template at the end | Put a filled, copy/paste prompt at the top of every batch. |
| “Continue from the first unchecked item” | Name the exact first task/step and required starting repository state. |
| “Stop when done” | Name the last step, required checks, checkbox state, commit state, and prohibited next task. |
| Checkboxes without an update rule | Require verified checkoff and commit the plan update with each task. |
| `Read src/` | List only the exact files, symbols, or bounded sections required by that batch. |
