# AGENTS.md

Shared working agreement for AI coding agents — all harnesses, all repos — readable by humans too. Canonical copy: `<agent-root>\AGENTS.md` (see Environment, bottom).

**Revision: 2026-07-12** — bump this date on every edit.

- Asked whether this guidance is loaded: answer with the revision above from memory — never re-read just to answer. A wrong or missing answer means the harness adapter is broken; fix via `runbooks\harness-setup\`, then re-read.
- Re-read the full file only when it was edited mid-session, post-compaction behavior drifts from these rules, or on a fresh machine/harness. For a single violation, cite the specific rule — targeted correction beats reloading.
- Admission test for new rules here: changes agent behavior, non-obvious to a current model, applies across repos, fits in ~2 lines. Repo-specific conventions go in that repo's own AGENTS.md. Guidance that recurs across sessions gets promoted into a rule.

## Operating Protocol

- Treat the user as a technical collaborator. Be direct: name real risks, weak architecture, and bad tradeoffs plainly — never hide a tradeoff to keep momentum.
- When rules conflict — with each other, with framework conventions, with local patterns — surface the conflict and recommend a path; never resolve it silently. This clause covers every rule below; individual rules don't restate it.
- Ambiguous requirements: present options with a recommendation before acting. Never ask a question a recommendation would unblock.
- Broader improvement nearby but out of scope: state cost and payoff; expand only on approval.
- Match depth to risk: concise for simple tasks; full reasoning, tradeoffs, and verification detail for complex or risky ones — enough that the result can be trusted.

## Architecture

- Apply SOLID; when its principles conflict in a design, analyze the tradeoff explicitly before committing to a direction.
- Decide state ownership before class structure (next section).
- Split a class when its responsibilities have different owners, change rates, or consumers — never by size or count. One coherent large class beats collaborators that leak its behavior back out through callbacks and getters. Class count measures nothing; decomposition worked when each unit owns its state and constructors display real coupling.
- Introduce an interface only at a genuine substitution point — second implementation, test boundary, dependency inversion. Prefer structural/duck typing where the language has it. No speculative abstraction: no interfaces, hierarchies, or configuration without a current second consumer.
- Build for the current requirement (YAGNI). Record deferred features as decisions with rationale, not omissions.
- If local patterns are weak, prefer the better pattern even at the cost of some inconsistency. Favor strong architecture even when it means a larger refactor — present scope and payoff before broad structural changes.
- Start from clean design; compromise only where real engine, toolchain, or build constraints force it.
- Dependency decisions — reuse, wrap, replace, or new abstraction — get a recommendation with the tradeoff.

## State Ownership

- Every piece of shared state has exactly one owner; consumers read through the owner and never keep copies.
- Ephemeral interaction state (drag anchors, hover, in-progress edits) stays out of shared owners.
- Values crossing thread, process, FFI, or undo boundaries are immutable — structurally, collections included, not just shallowly.
- Workflows spanning multiple owners are explicit named commands with a decided consistency story — never emergent from signal/event choreography.
- Hard behaviors — cancellation, undo granularity, atomicity, precision — get their own named contracts; no pattern provides them free.

## Error Handling

Classify the failure first; no blanket rule:

- Programmer errors (wiring mistakes, broken invariants, missing required dependencies): fail fast — raise or assert. Never quiet-return past them; never type a required dependency as optional. A silent no-op guard on a required dependency is a wiring error disguised as control flow.
- Expected runtime failures (corrupt file, unwritable path, bad input): log once at the failure site with context, then surface to the user through the designated channel. Quiet guard macros exist for this tier only.
- Missing capability (optional subsystem, unavailable backend): check once at startup; afterward features refuse explicitly with a clear message rather than silently doing nothing.
- Keep the happy path simple, but never hide important failure modes.

## Enforcement

- An architectural rule that is not machine-checked does not exist across sessions. Establish the rule and its check in the same change.
- A qualifying check runs in CI, fails on violation, has a planted-violation test proving it fires, and fails loudly if it scans nothing.
- Size and count gates are tripwires forcing a human decision (allowlist plus justification), never verdicts.
- Per-ecosystem recipes (Python AST guards, Unreal module-dependency enforcement, TypeScript boundary rules, CI patterns): `skills\architecture-guards\SKILL.md`.

## Code Style

- Names: explicit, descriptive, grammatically sensible — correct part of speech for the construct.
- Short functions that read like prose, named so the call site reads as intent. Short is the outcome of a single clear purpose, not a target: never split a coherent function to hit a length; never scatter one behavior across helpers that mean nothing alone.
- Low parameter counts for ordinary functions. Constructors are exempt — a constructor declares the unit's full coupling. Never hide a dependency behind a getter, callback, service locator, or context object to shrink a signature; a wide constructor is the god-object early-warning system working as intended.
- Prefer the repo guard/logging macros (`RETURN_FALSE_IF`, `RETURN_FALSE_QUIETLY_IF`, `RETURN_IF_FALSE`, `RETURN_QUIETLY_IF`, `CONTINUE_IF`, `CONTINUE_QUIETLY_IF`) over 5+ line if/log/return blocks. Log at the lowest level with enough context to diagnose, then propagate silently through callers via quiet guards — one error, logged once (expected-failure tier only; see Error Handling).
- Organize every file so the first screen tells the story: public API and core flow on top, helpers below; documents lead with a summary. Length is fine when organization keeps it scannable.
- Prefer prototypes, definitions, and calls on one line; split only when a line is genuinely hard to read or fights tooling.
- `.cpp` files: core class functionality at top, local helper bodies at bottom, compact forward declarations where C++ needs names early. Definition order mirrors the `.h` prototype order.
- Clear code first; comment only non-obvious intent and constraints.
- Refactor duplication early: a meaningful pattern appearing twice means look for the right abstraction.

## Class Layout

Order: lifecycle/dunder → fields and properties → public → protected → private.

- Group by role and audience within a section: user-facing/runtime APIs uninterrupted by persistence-only or internal support methods; helpers below.
- Blueprint-callable functions first in their section with a blank line between each; non-Blueprint prototype blocks stay tight, no blank lines.
- Within a visibility section, stable intentional order over accidental insertion order.

## Testing & Verification

- TDD when practical. Small focused tests; parameterized when it cuts duplication without hiding intent.
- Catch regressions aggressively before merge.
- Recommend the verification level from the scope and risk of the change.
- Never claim a step or fix is done without running its verification and showing the result.
- UX and performance targets are acceptance tests bound to a reference configuration (machine, input size, workload) — otherwise they are aspirations.
- Verify UX with deterministic artifacts — screenshots or recordings driven by fake completion signals, never timing sleeps — not prose claims.
- Design the failure-path UX (unavailable capability, corrupt data, refused action) up front; it is part of the feature.

## Process Weight, Specs & Plans

- At task start, recommend the process weight: direct implementation, written plan, or spec plus independent review. Spec + review for multi-session work or architecture other work builds on.
- Specs record decisions AND rejected counterfactuals with rationale ("more X would hurt because…") so future sessions don't "fix" deliberate choices.
- Treat independent review findings as claims: verify each against the code, fold accepted ones into the spec, record dispositions including pushback.
- Plans use bite-sized tasks with exact file paths and interfaces; every task carries one Claude and one Codex model recommendation matched to its difficulty.
- Executing a plan file: flip each step's checkbox to `- [x]` as the step completes, in the same edit burst as its verification — subagents included. A finished step with an unchecked box is an unfinished step.
- Session todo lists mirror the plan at task granularity — ≤7 coarse items, never sub-steps. Batch updates: mark completions when a burst of work lands, not after every action; each update re-emits the entire list. The plan file is the durable record, the todo list is disposable display — never maintain fine-grained state in both.

## Git & Change Safety

- No destructive or hard-to-undo source control moves without clear justification; avoid risky operations when a safe path exists.
- Be proactive about commits and pull requests when work is truly ready.
- In-progress work may be reorganized when it clearly helps the task — call out conflicts and risky rewrites first; preserve user intent.

## Review Order

Correctness, regressions, and behavioral risk → architecture and maintainability → coverage gaps, rollout, operational risk. Lead with the highest-risk issue; don't let style comments crowd out material engineering risk.

## Build, Release & Perforce

- Choose workflows by blast radius, rerun cost, and system risk. Favor repeatable, understandable steps; be explicit about assumptions, artifact names, paths, and verification.
- Perforce stream workspaces: run `p4 info` and `p4 where <file>` before assuming a file can be opened or submitted from the current client.
- If `p4 where` maps through an imported/parent stream and `p4 edit` says `file(s) not on client`: stop retrying path variants; name the stream-view issue and ask whether a different client, stream, or local-only patch is intended.
- Patch a file locally without opening it only when it is writable and the user explicitly wants a local test — and call out that the result may not be submit-ready from that client.

## Scout Repo Commands

*(Scout-specific — relocation candidate per the admission test: belongs in that repo's own AGENTS.md.)*

- Prefer Builder scripts over direct Unreal tooling: from `d:\p4\ss` run `python root/builder/src/<script>.py`; from `d:\p4\ss\root` run `python builder/src/<script>.py`.
- Build: `build_game.py`. Project files: `generate_project_files.py --repo-root root`. All automation tests: `run_automation_tests.py --repo-root root`; focused runs append test names/prefixes (e.g. `Scout.AssetTracker`).
- Builder finds the repo root via `UnrealPathFinder`; default logs land in `<repo-root>/scout_logs`.
- "Live Coding active" reported after Unreal is closed: check for stale editor processes before retrying.

## Environment & Harness Adapters

- `<agent-root>` = this directory's absolute path: `C:\git\worky\Agent` or `D:\git\worky\Agent` depending on machine.
- Layout: shared guidance here; skills in `skills\<name>\SKILL.md`; runbooks in `runbooks\<workflow>\`. Harness integration is always a symlink/junction back to `<agent-root>`, never a copy. Setup steps and per-harness paths: `runbooks\harness-setup\`.
- An explicitly requested `@skill <name>` missing from the active skill list: check `<agent-root>\skills\<name>\SKILL.md` before reporting it unavailable — if present, read it fully and follow it. Likewise check `runbooks\<workflow-name>\` before assuming a named workflow is project-local.
- When a skill and a runbook describe the same workflow, update both in the same change.
