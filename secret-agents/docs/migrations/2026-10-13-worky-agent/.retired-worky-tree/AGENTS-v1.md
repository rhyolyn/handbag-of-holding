# AGENTS.md

This file captures collaboration preferences, engineering standards, and working defaults for this repository. It is written for AI coding agents first, but it should also be readable and useful to human collaborators.

**Revision: 2026-07-11b** — bump this date on every edit to this file.

## When To Ask An Agent To Read This File

This file is normally auto-loaded at session start through the harness adapters below, so a read request at startup is usually redundant. Use this decision rule:

- **Verify before re-reading:** ask "what revision of the shared guidance is loaded?" A correct answer proves it loaded; a wrong or missing one means the adapter is broken on this harness or machine — fix the symlink, then ask for a read.
- **Ask for a re-read when:** this file was edited mid-session; the session is long enough that context was compacted and behavior starts drifting from a rule here; or a harness/machine is newly set up.
- **Don't re-read for a single violation:** if behavior contradicts one rule, name the rule and section — a targeted correction beats reloading the whole file.

Agents: when asked whether this guidance is loaded, answer with the revision date above from memory — do not re-read to answer. When told to re-read, read the entire file, not a summary or the first section.

## Purpose

- Preserve user preferences across sessions.
- Reduce repeated onboarding and avoid re-litigating known working agreements.
- Favor good architecture, safe change management, and direct communication.

## Harnesses

- The directory containing this file is the canonical source of truth for shared agent guidance, portable skills, and shared runbooks. This file refers to it as `<agent-root>`; resolve it per machine via Known Locations below.
- Keep shared guidance in `AGENTS.md`.
- Keep shared skills in `skills\<skill-name>\SKILL.md`.
- Keep shared runbooks in `runbooks\<workflow-name>\*.md`.
- Prefer open-standard filenames and layouts so the same content works across harnesses without rewrites.
- Do not copy shared guidance, skills, or runbooks into harness-specific folders when a symlink or junction will work.
- Treat harness-specific files and directories as adapters that point back to this directory.

### Canonical Layout

- `AGENTS.md` is the shared instruction file.
- `skills\` contains one subdirectory per skill.
- Each skill directory should contain a top-level `SKILL.md`.
- Optional skill assets should live under `references\`, `scripts\`, or `assets\` inside the skill directory.
- `runbooks\` contains one subdirectory per reusable workflow.
- Runbooks should be project-agnostic unless explicitly labeled as project defaults.

### Known Locations

`<agent-root>` means this directory's absolute path on the current machine. This repo lives across two systems:

- `C:\git\worky\Agent`
- `D:\git\worky\Agent`

All in-repo references in this file are relative to `<agent-root>`. Symlinks and junctions cannot be relative across drives, so when creating adapters, resolve `<agent-root>` to the local path first.

### Harness Adapters

- For harnesses that support global `AGENTS.md`, create a file symlink from the harness-global location back to `<agent-root>\AGENTS.md`.
- For harnesses that support Agent Skills discovery, create a directory symlink or junction from the harness skill location to each shared skill directory, or to the shared `skills\` directory when the harness path is otherwise empty.
- If a harness requires a different instruction filename, prefer a symlink to `AGENTS.md` rather than maintaining a second real file.
- If a harness requires a different skill discovery path, point that path at this repository instead of duplicating skills.
- If a skill and runbook describe the same workflow, update both in the same change.

### Codex

- Global shared guidance path: `%USERPROFILE%\.codex\AGENTS.md` -> `<agent-root>\AGENTS.md`
- Home bootstrap path: `%USERPROFILE%\AGENTS.md` — lightweight setup instructions for all harnesses; on a configured machine this is a standalone file, not a symlink to this file. Prefer `%USERPROFILE%\.codex\AGENTS.md` for the canonical guidance link.
- Global user skill path: `%USERPROFILE%\.agents\skills\` -> `<agent-root>\skills\` (junction) or `%USERPROFILE%\.agents\skills\<skill-name>` -> `<agent-root>\skills\<skill-name>` (per-skill symlinks)
- When the user explicitly invokes `@skill <skill-name>` and that skill is not in Codex's active skill list, check `<agent-root>\skills\<skill-name>\SKILL.md` before reporting it unavailable. If present, read it fully and follow it.
- When a named workflow has a shared runbook, check `<agent-root>\runbooks\<workflow-name>` before assuming the workflow is project-local.
- If `%USERPROFILE%\.agents\skills` is empty, it is also acceptable to link the entire directory to `<agent-root>\skills`.
- If `%USERPROFILE%\.agents\skills` already contains other entries, add links per skill instead of replacing the whole directory.

### Claude

- Global shared guidance path: `%USERPROFILE%\.claude\AGENTS.md` -> `<agent-root>\AGENTS.md`
- Claude Code also discovers project-level AGENTS.md and CLAUDE.md files; AGENTS.md is preferred for cross-harness portability.
- Global user skill path: `%USERPROFILE%\.claude\skills\` -> `<agent-root>\skills\` (junction); worky skills use SKILL.md format and are invoked via the harness Skill tool.
- If `%USERPROFILE%\.claude\skills` is empty or absent, create a junction to `<agent-root>\skills` rather than per-skill symlinks so new skills appear automatically.

### Copilot

- Setup path TBD. Update this section once the Copilot user-level instruction file path is confirmed for each machine.

### Portability Rules

- Prefer `AGENTS.md` over `agent.md` for shared instructions.
- Prefer `SKILL.md` skills that follow the open Agent Skills structure.
- Keep harness-specific notes small and isolated so the shared content stays portable.
- When adding a new harness, update this section with the adapter path and discovery rule instead of forking the content.

## How To Work With The User

- Treat the user as a technical collaborator, not just a requester.
- Be direct. Do not sugarcoat real risks, weak architecture, or bad tradeoffs.
- Optimize for a balance of speed, caution, and explanation.
- When requirements are ambiguous, present options with a recommendation before acting.
- Adapt response depth to the task, but include enough reasoning and verification detail that the result can be trusted.
- If a broader improvement is nearby but not strictly required, present the tradeoff and let the user choose.

## Decision-Making Defaults

- Do not ignore architecture in the name of short-term speed.
- Prefer solutions with strong boundaries, clear responsibilities, and clean abstractions.
- If existing local patterns are weak, prefer the better pattern even if it introduces some inconsistency.
- If language or framework conventions conflict with preferred structure, call out the conflict and recommend a path rather than resolving it silently.
- For build, rollout, verification, and operationally sensitive work, recommend the workflow based on blast radius, rerun cost, and system risk.
- Build for the current requirement (YAGNI). When deferring a real feature, record the deferral as a decision with rationale, not an omission.

## Specs, Reviews, And Process Weight

- At task start, assess complexity and recommend the process weight up front: direct implementation, written plan, or spec plus independent review. Recommend spec + review for multi-session work or architecture other work will build on.
- Specs record decisions AND rejected counterfactuals with rationale ("more X would hurt because…"), so future sessions don't "fix" deliberate choices.
- Treat independent review findings as claims: verify each against the code before accepting, fold accepted findings back into the spec, and record dispositions including pushback.
- Implementation plans use bite-sized tasks with exact file paths and interfaces. Every task includes model recommendations — one Claude and one Codex option — matched to the task's difficulty.

## Git And Change Safety

- Avoid risky git moves.
- Be proactive about commits and pull requests when work is truly ready.
- Do not make destructive or hard-to-undo source control changes without clear justification.
- Existing local changes may be reorganized when it clearly helps complete the task, but call out conflicts or risky rewrites first.
- Treat shared workspace state carefully. Preserve user intent when touching in-progress work.

## Architecture Principles

- Follow SOLID principles.
- If SOLID principles conflict in a given design, analyze the tradeoff explicitly and present it to the user before committing to a direction.
- Decide state ownership before class structure (see State Ownership).
- Split a class when its responsibilities have different owners, change rates, or consumers — not by size or count. Prefer one coherent large class over several collaborators that share its behavior back out through callbacks and getters.
- Class count measures nothing in either direction. The evidence that decomposition worked: each unit owns its state and behavior, and constructors display real coupling.
- Introduce an interface at a genuine substitution point — a second implementation, a test boundary, a dependency inversion. Prefer structural/duck-typed interfaces where the language has them; do not build hierarchies for identification.
- Favor strong architecture even when it leads to larger refactors, but present the scope and payoff before making broad structural changes.
- Start from a clean design, then compromise where real engine, toolchain, or build constraints require it.
- For dependencies and reuse decisions, present the tradeoff and recommend whether to reuse, wrap, replace, or introduce a new abstraction.

## State Ownership

- Every piece of shared state has exactly one owner; consumers read through the owner and never keep copies.
- Ephemeral interaction state (drag anchors, hover, in-progress edits) stays out of shared owners.
- Values crossing thread, process, FFI, or undo boundaries are immutable — structurally, collections included, not just shallowly.
- Workflows spanning multiple state owners are explicit named commands with a decided consistency story; they must not emerge from signal/event choreography.
- Hard behaviors — cancellation, undo granularity, atomicity, precision — get their own named contracts. No architecture pattern provides them for free.

## Enforcement

- An architectural rule that is not machine-checked does not exist across sessions. Establish the rule and its check in the same change.
- A qualifying check runs in CI, fails on violation, has a planted-violation test proving it fires, and fails loudly if it scans nothing.
- Size and count gates are tripwires that force a human decision (allowlist plus justification), never verdicts.
- Per-ecosystem recipes (Python AST guards, Unreal module-dependency enforcement, TypeScript boundary rules, CI patterns) live in `skills\architecture-guards\SKILL.md`.

## Coding Style Preferences

- Names should be clear, human-readable, and grammatically sensible.
- Use clean coding conventions for concrete grammar and parts of speech in names.
- Prefer the repository guard/logging macros such as `RETURN_FALSE_IF`, `RETURN_FALSE_QUIETLY_IF`, `RETURN_IF_FALSE`, `RETURN_QUIETLY_IF`, `CONTINUE_IF`, and `CONTINUE_QUIETLY_IF` for simple early-exit checks instead of introducing long 5+ line `if` blocks with manual logging and returns.
- Log failures at the lowest level that has enough context to diagnose the problem, then propagate failure silently through callers with quiet guard macros so the same error is not duplicated up the stack. Quiet guards are for expected runtime failures only — never for missing required dependencies or broken invariants; those fail fast (see Error Handling).
- Prefer explicit, descriptive names over short names.
- Strongly prefer short functions that read like prose — understandable at a glance, named so the call site reads as intent. Short is the outcome of a single clear purpose, not a target: never split a coherent function mechanically to hit a length, and never scatter one behavior across helpers that mean nothing alone.
- Keep parameter counts low for ordinary functions. Constructors are exempt: a constructor declares the unit's full coupling explicitly. Never hide a dependency behind a getter, callback, service locator, or context object to shrink a signature — a wide constructor is the god-object early-warning system working as intended.
- Organize every file so the first screen tells the story: public API and core flow at the top, helpers below; documents lead with a summary. Length is acceptable when organization makes it scannable.
- Favor clear code first, then document non-obvious intent and constraints.
- Refactor duplication early. If a meaningful pattern appears twice, look for the right abstraction.
- Prefer keeping prototypes, function definitions, and function calls on a single line when practical.
- Avoid splitting lines unless a single line becomes genuinely hard to read or conflicts with tooling.
- In `.cpp` files, prefer core class functionality near the top and local helper function bodies at the bottom; use compact forward declarations when C++ requires names before use.

## Class Organization

When language and local style make it reasonable, organize classes in this order:

1. Dunder methods or language-equivalent lifecycle methods
2. Properties and field-like declarations
3. Public methods
4. Protected methods
5. Private methods

If this ordering conflicts with strong local framework conventions, surface the conflict and recommend the best path.

- Keep function and prototype ordering tidy and intention-revealing.
- Group declarations by role and audience so public runtime or user-facing APIs are not interrupted by persistence-only or internal support methods.
- Within a visibility section, prefer stable, readable ordering over accidental insertion order.
- Put Blueprint-callable functions at the top of their class section so editor-facing APIs are easy to find.
- Put helper and persistence-only prototypes below the user-facing or Blueprint-facing APIs.
- Use a blank line between Blueprint-callable function declarations for readability.
- Do not add blank lines between adjacent non-Blueprint function prototypes; keep non-BP prototype blocks tight.
- Keep `.cpp` function definition order aligned with the corresponding `.h` prototype order.

## Error Handling

- Do not apply one blanket rule everywhere; classify the failure first:
  - Programmer errors (wiring mistakes, broken invariants, missing required dependencies) fail fast — raise or assert; never quiet-return past them, and never type a required dependency as optional.
  - Expected runtime failures (corrupt file, unwritable path, bad input) log once at the failure site with context, then surface to the user through the designated channel; quiet guard macros exist for this tier only.
  - Missing capability (optional subsystem, unavailable backend) is checked once at startup; afterward features refuse explicitly with a clear message rather than silently doing nothing.
- Keep the happy path simple when possible, but do not hide important failure modes.

## Testing And Verification

- Prefer TDD when practical.
- Keep tests small and focused.
- Prefer parameterized tests when they reduce duplication without making intent harder to read.
- Prioritize catching regressions aggressively before merge.
- In review, balance bugs, maintainability, and test gaps, but call out the highest-risk issue first.
- For verification level, present options and recommend the right level based on the scope and risk of the change.
- UX and performance targets are acceptance tests bound to a reference configuration (machine, input size, workload); otherwise they are aspirations.
- Verify UX with artifacts — screenshots or recordings generated deterministically (fake completion signals, never timing sleeps) — rather than prose claims that it works.
- Design the failure-path UX (unavailable capability, corrupt data, refused action) up front; it is part of the feature, not an afterthought.

## Review Priorities

- First priority: correctness, regressions, and behavioral risk.
- Second priority: architecture and maintainability.
- Third priority: test coverage gaps, rollout concerns, and operational risk.
- Do not let style comments crowd out material engineering risks.

## Build And Release Work

- Recommend workflows based on what can break and how expensive reruns are.
- Favor repeatable and understandable release steps.
- Be explicit about assumptions, artifact names, paths, and verification steps when working on build or release tasks.
- For Perforce stream workspaces, run `p4 info` and `p4 where <file>` before assuming a file can be opened or submitted from the current client.
- If `p4 where` maps a file through an imported or parent stream and `p4 edit` says `file(s) not on client`, do not keep retrying path variants; note the stream-view issue and ask whether a different client, stream, or manual local-only patch is intended.
- Only patch a Perforce file locally without opening it when the file is writable and the user explicitly wants a local test/change; call out that the change may not be submit-ready from that client.

## Repo Builder Commands

- Prefer the Builder-based scripts in `root/builder/src` instead of calling Unreal build tools directly.
- From the shared workspace root (`d:\p4\ss`), call scripts as `python root/builder/src/<script>.py`.
- From the Unreal repo root (`d:\p4\ss\root`), call scripts as `python builder/src/<script>.py`.
- `Builder` discovers the Unreal repo root through `UnrealPathFinder` and writes default logs under `<repo-root>/scout_logs`.
- Build the game/editor target with `python root/builder/src/build_game.py`.
- Run all Scout automation tests with `python root/builder/src/run_automation_tests.py --repo-root root`.
- Run focused automation tests by passing test names or prefixes as positional args, for example `python root/builder/src/run_automation_tests.py --repo-root root Scout.AssetTracker`.
- Generate project files with `python root/builder/src/generate_project_files.py --repo-root root`.
- If a build reports Live Coding is active even after Unreal is closed, check for stale Unreal/editor processes before retrying.

## Communication Preferences

- Be concise when the task is simple.
- Go deep on reasoning, tradeoffs, and verification details when the task is complex or risky.
- Use a direct tone for code review and technical critique.
- When uncertain, show the options, recommend one, and explain why.

## Repo-Specific Guidance

- Add concrete repository conventions here as they become stable enough to standardize.
- Prefer updating this file when recurring guidance appears in multiple sessions

## Anti-Patterns To Avoid

- Ignoring architecture to get to a quick patch.
- Making risky git moves without necessity.
- Letting duplication spread when a real abstraction is already visible.
- Hiding important tradeoffs instead of surfacing them.
- Asking unnecessary questions when a recommendation would unblock the work.
- Speculative abstraction: interfaces, hierarchies, or configuration with no current second consumer.
- Splitting code to satisfy size heuristics rather than ownership and cohesion.
- Silent no-op guards on required dependencies — wiring errors disguised as control flow.
