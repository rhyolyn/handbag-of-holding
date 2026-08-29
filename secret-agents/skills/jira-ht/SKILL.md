---
name: jira-ht
description: Use when the user invokes @skill jira-ht as a shorthand alias for creating Jira tickets for human developers.
---

# jira-ht

This skill is a shorthand alias for jira-human-ticket-create.

## Behavior

1. Read `<skill base dir>\..\jira-human-ticket-create\SKILL.md`.
2. Follow that skill exactly.
3. Treat all user arguments passed to `@skill jira-ht` as arguments for `jira-human-ticket-create`.

## Examples

- `@skill jira-ht help`
- `@skill jira-ht create Jira ticket titled "Create a Perforce stream for Unreal 5.8.1"`
