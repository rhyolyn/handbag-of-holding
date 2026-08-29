---
name: jira-human-ticket-create
description: Use when creating Jira tickets intended for human developers, especially when the request includes a title and partial technical context and needs a structured template with minimal follow-up questions.
---

# Jira Human Ticket Create

Create Jira issues for human developers using a consistent intake structure, minimal clarifying questions, and safe defaults.

## Invocation Pattern

Use one of these forms:

- `@skill jira-human-ticket-create create Jira ticket titled "<title>"`
- `Use skill jira-human-ticket-create to create a Jira ticket titled "<title>"`

Do not repeat "human-targeted" in the prompt body. The skill name already scopes to human tickets.

If the user invokes help, do not create a ticket.

- Trigger: `@skill jira-human-ticket-create help`
- Behavior: print a concise help response with examples and expected inputs.

Help response should include at least:

- Purpose: creates Jira tickets for human developers from the standard template.
- Defaults: requester VIS Dev, issue type Task, timeline Flexible, assignee Unassigned.
- Required inputs: title, what, why, done criteria.
- Example create commands.

## Defaults

- Requester/team: `VIS Dev`
- Timeline: `Flexible`
- Issue type: `Task`
- Assignee: `Unassigned`
- Priority: do not force-set unless explicitly requested
- Labels: `human-targeted`, `intake`

## Template Selection

- Use Engineering template when work is code, build, infra, tooling, or technical delivery.
- Use Lightweight template for simple requests, coordination, or admin work.

## Template Sources (Source of Truth)

Load templates from the vault instead of copying inline text. This keeps one authoritative version.

- Engineering template source: `<skill base dir>\..\..\..\Work Intake System\Templates\Engineering Task Template.md`
- Lightweight template source: `<skill base dir>\..\..\..\Work Intake System\Templates\Lightweight Intake Template.md`

When creating a ticket:

1. Read the selected template file from the paths above.
2. Build the Jira description from that file.
3. Apply defaults and user-provided details.
4. Do not hardcode template body in this skill.

If template files are unavailable, abort ticket creation and report the missing path(s).

## Required Information

Collect or infer these before creation:

- Title
- Why this matters
- What should be done
- Done criteria (measurable)

If required information is missing, ask only the minimum needed.

## Minimal Question Flow

Ask at most these, in order, and stop when sufficient:

1. Project key (only if unknown)
2. Confirm issue type (only if non-Task likely)
3. Due date (only if timeline is constrained)
4. Assignee (only if user asks for assignment now)
5. Extra acceptance criteria (optional)

If the user does not answer optional items, proceed with defaults.

## Template Rendering Rules

- Keep section headings exactly as defined in the selected template source.
- Replace placeholder defaults only when concrete values are known.
- Preserve checklist formatting for acceptance criteria.
- Keep requester default as VIS Dev unless user provides a different requester.

## Quality Checks Before Create

- Includes all required sections for the selected template.
- Acceptance criteria are measurable and outcome-based.
- No unresolved placeholders when concrete details are known.

## Creation Behavior

1. Attempt to create the issue with summary, description, issue type, and labels.
2. If project rejects priority, retry without priority.
3. Return issue key, URL, template used, and assumptions.

## Fallback Behavior (No Jira API Access)

If direct Jira creation is unavailable, produce:

- A final issue body ready to paste into Jira
- Suggested issue type and labels
- A short checklist of fields user must set manually

If template source files are unavailable, abort and report:

- "Template source unavailable, ticket creation aborted"
- Missing path(s)
- Suggested fix: restore template files under Work Intake System/Templates and retry

## Response Format

After create, report:

- Created: `<ISSUE-KEY>`
- URL: `<issue-url>`
- Template used: `Engineering` or `Lightweight`
- Assumptions applied: bullet list
- Follow-ups needed: bullet list (or `None`)

## Example

`@skill jira-human-ticket-create create Jira ticket titled "Create a Perforce stream for Unreal 5.8.1". Task: create the stream and populate from Epic UE5 5.8.1 latest stream on ssl:p4-licensee.epicgames.com:1666. Done when Unreal compiles and launches from built binaries.`
