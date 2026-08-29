# Worky Agent Skills

The shared, harness-portable skill set for this vault. Each skill is one directory under `<agent-root>\skills\` with a top-level `SKILL.md` following the open Agent Skills structure; harnesses discover them through junctions, never copies (see `runbooks\harness-setup\harness-setup.md`). This README explains how and when to use each skill, how to call it from Claude, Codex, and Copilot, and gives an engineering review of each — plus a cross-cutting look at harness coverage, gaps, and token-costly mistakes.

*Generated 2026-08-29 by `update-skills-readme`. Markdown is the source of truth; `README.html` is rendered from it — regenerate with `/update-skills-readme`, don't hand-edit the HTML.*

## Table of Contents

- [How skills are wired and invoked](#how-skills-are-wired-and-invoked)
- [Skill inventory](#skill-inventory)
- Skills
  - [agent-plan](#agent-plan)
  - [agent-preflight](#agent-preflight)
  - [clean-code-architecture-guards](#clean-code-architecture-guards)
  - [clean-code-error-handling](#clean-code-error-handling)
  - [jira-ht](#jira-ht)
  - [jira-human-ticket-create](#jira-human-ticket-create)
  - [python-quality-gate](#python-quality-gate)
  - [python-tdd-cycle](#python-tdd-cycle)
  - [ready-player-one](#ready-player-one)
  - [report-receipt](#report-receipt)
  - [report-rollup](#report-rollup)
  - [report-status](#report-status)
  - [unreal-reset-build-env](#unreal-reset-build-env)
  - [unreal-ugs-release](#unreal-ugs-release)
  - [update-claude-pricing-doc](#update-claude-pricing-doc)
  - [update-model-routing](#update-model-routing)
  - [update-skills-readme](#update-skills-readme)
- [Architect's overview](#architects-overview)
  - [Harness coverage matrix](#harness-coverage-matrix)
  - [Skill gaps](#skill-gaps)
  - [Token-costly mistakes](#token-costly-mistakes)
- [Maintaining this document](#maintaining-this-document)

## How skills are wired and invoked

One skill body, three call conventions. The content is identical everywhere because harness integration is always a symlink/junction back to `<agent-root>` (`C:\git\worky\Agent` or `D:\git\worky\Agent` depending on machine).

### Claude (Claude Code)

- **Discovery:** `%USERPROFILE%\.claude\skills\` is a whole-directory junction to `<agent-root>\skills\` (verified live on this machine 2026-07-12). New skills appear automatically. Shared guidance links via `%USERPROFILE%\.claude\AGENTS.md`.
- **Call formats:**
  - *Automatic* — Claude matches the task against each skill's `description:` frontmatter and invokes it through the built-in Skill tool. This is the primary path; write descriptions as triggers.
  - *Slash command* — `/skill-name args`, e.g. `/report-rollup month 2026-06`. Arguments are free text passed to the skill.
  - *Explicit mention* — `@skill <name>` in a prompt. This is the vault's cross-harness convention (AGENTS.md § Environment): if the name is missing from the active skill list, the agent must check `<agent-root>\skills\<name>\SKILL.md` before reporting it unavailable.
- **Verify wiring:** ask "what revision of the shared guidance is loaded?" — a correct AGENTS.md revision date proves the adapter works.

### Codex

- **Discovery:** `%USERPROFILE%\.agents\skills\` is a junction to `<agent-root>\skills\` (verified live on this machine 2026-07-12); per-skill links under `%USERPROFILE%\.codex\skills\<name>` also work. Shared guidance links via `%USERPROFILE%\.codex\AGENTS.md`. Restart Codex after adding links.
- **Call formats:** no slash-command surface — name the skill in the prompt using the `@skill <name>` convention (e.g. `@skill report-rollup month 2026-06`) or describe the task and let description matching fire. The AGENTS.md fallback rule applies: an explicitly requested skill missing from the active list means "read `<agent-root>\skills\<name>\SKILL.md` and follow it", not "unavailable".
- **Trust note:** Codex stops on approval prompts unless the project is trusted in `%USERPROFILE%\.codex\config.toml` (`trust_level = "trusted"`); agent-preflight's Check 2 verifies this.

### Copilot

- **Discovery:** not wired yet — `harness-setup.md` lists the Copilot section as *"Setup path TBD."* No skill in this set is natively reachable from Copilot today.
- **Interim call format:** reference the file explicitly — in VS Code Copilot Chat, attach `Agent\skills\<name>\SKILL.md` (`#file:` or paste the path) and instruct: "Read this skill and follow it exactly for <task>."
- **Recommended fix:** add a repo-level `.github/copilot-instructions.md` pointing at `AGENTS.md` and the skills directory, then record the adapter in `harness-setup.md`.

## Skill inventory

Model column: pick the cheapest model that does the job — recommendations marked § come from the skill's own text; the rest are architect suggestions.

| Skill | Kind | Parameters | Model (Claude / Codex) | One-liner |
|---|---|---|---|---|
| [agent-plan](#agent-plan) | planning workflow | none | Sonnet / medium | Make resumable, model-routed execution plans |
| [agent-preflight](#agent-preflight) | preflight | none (auto-detects) | Haiku / o4-mini § | Binary ready/NOT-READY check before batched prompts |
| [clean-code-architecture-guards](#clean-code-architecture-guards) | reference | none | Sonnet / medium | Turn architecture rules into CI-enforced checks |
| [clean-code-error-handling](#clean-code-error-handling) | technique | none | Sonnet / medium | Design or refactor semantic error contracts without accidental behavior changes |
| [jira-ht](#jira-ht) | alias | ticket-create arguments | Sonnet / medium | Short alias for creating human-developer Jira tickets |
| [jira-human-ticket-create](#jira-human-ticket-create) | workflow | `help` or ticket details | Sonnet / medium | Create structured Jira tickets for human developers |
| [python-quality-gate](#python-quality-gate) | gate | none | Haiku / low | mypy → ruff check → format check → pytest, all clean before commit |
| [python-tdd-cycle](#python-tdd-cycle) | process | none | Sonnet / medium | Red-green loop with observed failure before implementation |
| [ready-player-one](#ready-player-one) | alias | agent-preflight arguments | Haiku / o4-mini § | Fun alias for the agent-preflight check |
| [report-receipt](#report-receipt) | generator | verbatim-text option | Sonnet § / low § | Work receipt with cost analysis and efficiency coaching |
| [report-rollup](#report-rollup) | generator | `month YYYY-MM` \| `year YYYY` (required) | Sonnet / medium | Roll status reports into monthly or annual documents |
| [report-status](#report-status) | generator | `window <start>..<end>` (optional) | Sonnet / medium | Tue/Thu status report compiled from work receipts |
| [unreal-reset-build-env](#unreal-reset-build-env) | script wrapper | script flags (see section) | Haiku / low | Stop Unreal build processes and clean shell env on Windows |
| [unreal-ugs-release](#unreal-ugs-release) | domain workflow | profile overrides | Opus+ / high | Build, validate, and submit UGS precompiled editor binaries |
| [update-claude-pricing-doc](#update-claude-pricing-doc) | utility | none | Haiku § / — | Refresh the cached Claude pricing JSON |
| [update-model-routing](#update-model-routing) | utility | none | Sonnet / medium | Check or refresh centralized model-routing metadata |
| [update-skills-readme](#update-skills-readme) | meta | `review` (optional) | Sonnet; frontier with `review` | Regenerate this README (MD + HTML) from the skill set |

---

### agent-plan

**What it does.** Produces durable, resumable implementation plans with explicit model-routing profiles, context-cohesive batches, and copy/paste handoffs for later agents or sessions.

**When to use.** When creating or revising a plan that spans agents or sessions and needs efficient routing and durable progress tracking.

**Parameters.** None. It reads the centralized model-routing reference and requires a current staleness check.

**Examples.**
- Claude: `@skill agent-plan — plan the cross-platform harness rollout in resumable batches.`
- Codex: `@skill agent-plan — write an implementation plan with model-routed handoffs.`
- Copilot: attach `Agent\skills\agent-plan\SKILL.md` → "Create a durable, batch-oriented execution plan."

> Review pending — rerun with "review".

### agent-preflight

**What it does.** Pre-flight environment check before executing a batched prompt: detects harness (claude/codex/copilot) and OS, reports the active model against a cost-optimal recommendation, then runs three gates — skill visibility, execution trust (permission mode / project trust), and uv health + no locked build executables. Binary outcome: `ready` or `NOT READY` with a numbered, OS- and harness-specific remediation list. Strict output contract (blocks reproduced exactly) so headless logs are diffable.

**When to use.** Before handing any batched prompt or long autonomous task to a model — it front-loads the failures that would otherwise stall an unattended run.

**Parameters.** None; harness, OS, and model are auto-detected. Check 3b derives the project executable name from the working directory — override manually when the artifact name differs.

**Examples.**
- Claude: `/agent-preflight` (then paste the batched prompt once it prints `ready`)
- Codex: `@skill agent-preflight — preflight before this batch.`
- Copilot: attach the SKILL.md → "Run this preflight and print the summary block."

**Architect's review.**
- *Strengths:* The strict output contract is the standout design decision — deterministic, diffable, no model editorializing. Remediation is specific (exact file, exact key, exact command) per OS *and* harness. The model-recommendation step is cost-awareness built into the process. Placeholders for unknown Copilot mechanics are honest rather than invented.
- *Weaknesses:* Field-tested 2026-07-12 and two cracks showed. (1) Check 2 demands the literal key in both project and global settings, but Claude settings inherit — global `dontAsk` with no project file is effectively `dontAsk`, yet the check fails; worse, the auto-mode classifier *denies agents writing that key* (self-escalation guard), so the skill prescribes a remediation an agent cannot perform and then forbids proceeding: an autonomous dead-end. (2) The "restart on haiku" advice is wrong when the preflight runs inline before a complex batch in the same session — a restart would throw away the correctly-chosen model. Also: the uv check runs even in repos where uv is irrelevant, and the dir-name exe heuristic is a permanent no-op in non-build repos (`worky.exe` will never exist).
- *Improvements:* Test effective permission mode (project value *or* inherited global) instead of file literals, and mark Check-2 remediation "human-only: classifier blocks agent self-service." Scope the model warning to standalone checklist runs. Gate Check 3 on project type (presence of `pyproject.toml`/`uv.lock`; build-artifact check only where a build exists). Fill the Copilot placeholders when the adapter lands.

### clean-code-architecture-guards

**What it does.** Reference recipes for converting architectural rules — layer boundaries, import direction, deleted-module bans, size tripwires — into machine-checked CI guards. Includes a Python AST import scanner, Unreal `.Build.cs` dependency patterns, TypeScript eslint/dependency-cruiser rules, and the four properties every qualifying guard must have (runs in CI, named for its rule, planted-violation test, fails loudly on empty scan).

**When to use.** The moment an architectural rule exists only in prose, review feedback, or comments. Per AGENTS.md § Enforcement: a rule that is not machine-checked does not exist across sessions — establish rule and check in the same change. Not for one-off style preferences (linter config) or judgment calls (review checklists).

**Parameters.** None — it's a knowledge skill; you bring the rule, it brings the recipe.

**Examples.**
- Claude: `Use @skill clean-code-architecture-guards — enforce "views never import stores" as a pytest guard.`
- Codex: `@skill clean-code-architecture-guards: add an import-direction guard for src/views with a planted-violation test.`
- Copilot: attach `Agent\skills\clean-code-architecture-guards\SKILL.md` → "Follow this to add a layer-boundary test for views→stores."

**Architect's review.**
- *Strengths:* The four-property guard definition is genuinely excellent engineering doctrine — especially "fails loudly when it scans nothing," which kills the most expensive kind of green build. The planted-violation pattern means guards are themselves tested. Maps 1:1 onto AGENTS.md § Enforcement, so skill and standing rules can't drift apart. The per-ecosystem quick-reference table gives instant altitude before diving in.
- *Weaknesses:* The reference scanner exists only as an inline code block — every use re-types ~30 lines into a new repo instead of copying a shipped file. No CI-wiring example (the recipes end at the test; the "runs in CI" property is asserted, not demonstrated). Python gets a full implementation; Unreal and TS get prose.
- *Improvements:* Ship the scanner as `scripts/import_scanner.py` in the skill directory. Add one minimal CI snippet per ecosystem. Cross-link python-quality-gate as the local runner of these guards. Ironic gap worth closing: the skill set itself has no machine-checked guards (see [Skill gaps](#skill-gaps)).

### clean-code-error-handling

**What it does.** Provides a language-agnostic workflow for designing or refactoring error handling around semantic conditions, real consumer reactions, native language error mechanisms, preserved causes, single-point logging, presentation boundaries, and compatibility-first migration. It also defines when error types stay beside behavior, move into domain-owned modules, or require machine-enforced architecture checks.

**When to use.** When designing error handling or when a repository has inline messages, generic exceptions, duplicate logging, string-parsed failures, scattered error types, or unclear error ownership.

**Parameters.** None — provide the repository, subsystem, or files whose error handling should be designed or reorganized.

**Examples.**
- Claude: `@skill clean-code-error-handling — design the error model for this new payment workflow.`
- Codex: `@skill clean-code-error-handling: reorganize inline errors and duplicate logging under src/catalog.`
- Copilot: attach `Agent\skills\clean-code-error-handling\SKILL.md` → "Follow this to refactor the repository's error handling without changing its public responses."

> Review pending — rerun with "review".

### jira-ht

**What it does.** Provides a short alias for the jira-human-ticket-create workflow, forwarding every argument to that canonical skill.

**When to use.** When a requester invokes `@skill jira-ht` to create a Jira ticket for a human developer.

**Parameters.** The same arguments accepted by jira-human-ticket-create.

**Examples.**
- Claude: `@skill jira-ht create Jira ticket titled "Create a Perforce stream for Unreal 5.8.1"`
- Codex: `@skill jira-ht create Jira ticket titled "Document build recovery"`
- Copilot: attach `Agent\skills\jira-ht\SKILL.md` → "Use this alias to create the requested Jira ticket."

> Review pending — rerun with "review".

### jira-human-ticket-create

**What it does.** Creates Jira issues for human developers from the vault's Engineering or Lightweight intake template, applying safe defaults and producing a paste-ready fallback when Jira access is unavailable.

**When to use.** When creating a human-developer Jira ticket from a title and partial technical context.

**Parameters.** `help` for usage, or ticket details including title, why, work, and measurable done criteria.

**Examples.**
- Claude: `@skill jira-human-ticket-create create Jira ticket titled "Create a Perforce stream for Unreal 5.8.1"`
- Codex: `@skill jira-human-ticket-create create Jira ticket titled "Fix CI package discovery"`
- Copilot: attach `Agent\skills\jira-human-ticket-create\SKILL.md` → "Create a Task using the Engineering template."

> Review pending — rerun with "review".

### python-quality-gate

**What it does.** Runs the four-tool gate in strict order — `mypy`, `ruff check`, `ruff format --check`, `pytest` — and requires all four to exit clean before any commit. Includes exact pass-criteria strings, a never-suppress policy (`# type: ignore` / `# noqa` need explicit user approval), and observed fix patterns for common mypy/ruff findings.

**When to use.** Before committing any Python change; after every violation fix (re-run the full gate, not just the offending tool); as a final pre-PR check.

**Parameters.** None. Substitute `uv run` for `python -m` when uv is healthy.

**Examples.**
- Claude: `Run @skill python-quality-gate before committing.` (also auto-triggers on Python commit intent)
- Codex: `@skill python-quality-gate — run the gate and fix violations, no suppressions.`
- Copilot: attach the SKILL.md → "Run these four commands in order and fix everything they flag."

**Architect's review.**
- *Strengths:* Ordering (types → lint → format → tests) fails fast on the cheapest tools first. Exact expected output strings prevent "close enough" passes. The never-suppress policy with a surface-to-user escape hatch is the right default; the documented project fix patterns (B008 sentinel, `findChild` assertion) save real debugging time.
- *Weaknesses:* Hard-codes the `src/ tests/` layout, and the `ugs.exe` lock advice is project baggage in a shared skill — AGENTS.md's own admission test says repo-specific conventions belong in that repo's AGENTS.md. No mention of the write-mode `ruff format` fast path (fix then verify with `--check`). Assumes mypy is configured; silent no-op if a repo lacks `[tool.mypy]`.
- *Improvements:* Read paths from `pyproject.toml` or accept them as an argument. Move the ugs.exe fallback note to the ugs repo. Add "if format check fails: run `ruff format`, then re-run the full gate."

### python-tdd-cycle

**What it does.** Enforces the red-green loop for pytest projects: write the failing test, *observe* it fail, implement the minimum, observe green, then run the full suite before committing. Defines "done" as tests that were seen failing before implementation, with no skips or suppressions.

**When to use.** Every new feature or fix in a pytest-based Python project. Explicitly does not cover the commit itself.

**Parameters.** None.

**Examples.**
- Claude: `Implement the window-parsing fix with @skill python-tdd-cycle.`
- Codex: `@skill python-tdd-cycle — add receipt-date boundary handling, tests first.`
- Copilot: attach the SKILL.md → "Follow this loop for the new parser: failing test first, show me the red run."

**Architect's review.**
- *Strengths:* "Confirm red" is the step every agent (and human) skips, and this skill makes it non-negotiable — a test that passes before implementation is declared wrong, which catches tautological tests. Narrow-file-then-full-suite laddering keeps iteration fast. Clean scope boundary with the commit workflow.
- *Weaknesses:* Same `ugs.exe` project leak as the quality gate. No guidance for the place TDD actually dies: hard-to-test seams (Qt widgets, filesystem, subprocess). On Claude it overlaps `superpowers:test-driven-development` with no statement of precedence — two skills claiming the same loop invites inconsistent behavior.
- *Improvements:* Add a short seams section (fake the boundary, test the logic). Declare precedence explicitly ("on Claude, superpowers TDD governs process; this skill supplies the pytest specifics"). Move the Windows/uv note to the ugs repo's AGENTS.md.

### ready-player-one

**What it does.** Shorthand alias for agent-preflight — reads `<skill base dir>\..\agent-preflight\SKILL.md` and follows it exactly, forwarding any arguments. Kept because the codename is fun and muscle-memory-friendly ("Ready Player One: are we ready to start?").

**When to use.** Whenever you'd reach for agent-preflight but want the memorable name — `/ready-player-one` before a batched prompt.

**Parameters.** The same arguments accepted by agent-preflight (none required; harness/OS/model auto-detected).

**Examples.**
- Claude: `/ready-player-one`
- Codex: `@skill ready-player-one — preflight before this batch.`
- Copilot: attach `Agent\skills\ready-player-one\SKILL.md` → "Follow the agent-preflight skill it points to and print the summary block."

> Review pending — rerun with "review".

### report-receipt

**What it does.** Writes a work receipt — the vault's atomic record of engineering work — to `Receipts\YYYY\YYYY-MM\WR-YYYY-MM-DD_<topic-slug>.md` with a locked section structure: Goal, Changes, Files/Systems, Technical Decisions, Coordination, Risks, Handoff (a self-contained resume prompt for the next session), Suggested Status Bullet, and an Efficiency Analysis (actual prompt, hindsight-corrected prompt, AI cost analysis priced from the session transcript, and a human improvement plan that reads the *previous* receipt's plan and reports the delta). Appends a cost-ledger row. Returns only the path, a one-line summary, and the Efficiency Analysis — the file is the deliverable.

**When to use.** Whenever work should leave a trail: receipts, handoff notes, status/completion/progress summaries, preserving analysis verbatim, or on explicit `@skill report-receipt`. Receipts are the upstream feed for report-status.

**Parameters.** No formal arguments. Verbatim option: text the user wants preserved exactly goes in a fenced block, unmodified. Topic slug derives from the work.

**Examples.**
- Claude: `@skill report-receipt — receipt for today's shader-worker troubleshooting.`
- Codex: `@skill report-receipt — receipt for this session; work concluded today.`
- Copilot: attach the SKILL.md → "Produce the receipt exactly per Required Output Format; use an included model, not a premium request."

**Architect's review.**
- *Strengths:* The most harness-complete skill in the set — per-harness model recommendations *and* separate, semantically correct cost recipes for Claude (sum `.jsonl` usage fields, cache read 0.1×/write 1.25×) and Codex (cumulative `token_count` snapshots — never summed; quota ≠ dollars; no invented public rates). The coaching loop is the standout: each receipt grades the previous receipt's advice before issuing new advice, which is how coaching compounds instead of repeating. Output discipline ("the file is the deliverable") keeps chat cheap. Even the model-switching warning (cache invalidation can cost more than the pricier model) is correct and non-obvious.
- *Weaknesses:* The transcript read is the skill set's single largest hidden token sink — "parse each line as JSON" on a long session means pulling megabytes through the context window to sum four integers. No Copilot cost recipe (model recommendation only), so one leg of the tri-harness story is shorter than the other two. The instruction ordering (write prompts *before* reading the transcript, cost *after*) is subtle and easy for a rushed session to violate. Filename discipline exists because it was learned the hard way (the vault's `.md.md` cleanup) — good rule, but only prose enforces it.
- *Improvements:* Add `scripts/sum_usage.py` (stdlib-only, uv-run) that totals usage fields outside the context window and prints the four numbers — turns the biggest token cost in the vault into approximately zero. Add a Copilot cost stanza when a usage surface exists. When pricing is stale, auto-run update-claude-pricing-doc rather than only warning.

### report-rollup

**What it does.** Rolls status reports up into a monthly report (`monthly-YYYY-MM.md`) or an annual performance-review document (`Reviews\annual-YYYY.md`). Selects sources by frontmatter `window_end`, prefers monthly reports when building the annual, flags `status: draft` sources in a callout, writes fixed section structures per audience, appends a cost-ledger row, and prints an exact two-line output for headless log capture.

**When to use.** Month-end rollup, annual review prep, or when the scheduled monthly-rollup run fires.

**Parameters.** Exactly one, required — malformed or missing prints usage and stops:

| Argument | Window | Audience |
|---|---|---|
| `month YYYY-MM` | 1st 00:00 → next 1st 00:00 (Pacific) | Self + manager monthly summary |
| `year YYYY` | Jan 1 → Jan 1 (Pacific) | Performance review — impact framing, not a log |

**Examples.**
- Claude: `/report-rollup month 2026-06` · `/report-rollup year 2026`
- Codex: `@skill report-rollup month 2026-06`
- Copilot: attach the SKILL.md → "Run this with argument `month 2026-06`."

**Architect's review.**
- *Strengths:* Idempotency (existing output → skip, never overwrite) makes scheduled re-fires safe. Draft flagging propagates data-quality state instead of laundering it. The audience split is real editorial guidance — the annual's "impact, scope, growth narratives, not a chronological log" is exactly what performance-review material needs. Empty window still writes a document: absence of work is information.
- *Weaknesses:* Pacific offsets are hand-managed prose ("-07:00 PDT, -08:00 PST") — a DST-transition bug waiting for a model to make it. The cost-ledger header contract is duplicated across three skills (this, report-status, report-receipt); a header change is a three-file edit today. Window math and source-selection rules have no executable test — precisely the "rule in prose" the vault's own clean-code-architecture-guards skill warns about. No model recommendation despite being a scheduled, cost-sensitive run.
- *Improvements:* Extract a shared `scripts/` helper (window computation + ledger append) with pytest coverage, used by both report skills. Add a model line ("Sonnet-class; judgment is summarization"). Document the rerun-after-bad-output path (delete the file, rerun) since idempotency intentionally blocks regeneration.

### report-status

**What it does.** Generates one Tue/Thu status report from work receipts. Computes the reporting window from Tue/Thu 06:00 Pacific boundaries, chains `window_start` from the previous report's frontmatter (so missed schedules self-heal), collects receipts by filename end-date, fills a template-locked section structure, records receipt wikilinks as `sources`, appends a cost-ledger row, and prints an exact two-line output for headless logs. Idempotent per window.

**When to use.** When the scheduled Tue/Thu run fires, or on demand — including backfills via the window override.

**Parameters.** Optional: `window <start>..<end>` (e.g. `window 2026-07-07..2026-07-09`) — uses `<date>T06:00` local verbatim and skips automatic window computation.

**Examples.**
- Claude: `/report-status` · `/report-status window 2026-07-07..2026-07-09`
- Codex: `@skill report-status window 2026-07-07..2026-07-09`
- Copilot: attach the SKILL.md → "Generate the report for the window ending today."

**Architect's review.**
- *Strengths:* Deriving `window_start` from the last report instead of "today" is the best design decision in the report pipeline — catch-up runs after missed schedules are automatically correct, and re-runs are idempotent. Boundary semantics (the 06:00 comparisons, same-day receipt placement) are written out to the half-open-interval level. "No receipts" produces a real report — an empty period is information. The don't-invent-work rule keeps reports honest.
- *Weaknesses:* Same hand-rolled Pacific timezone risk and ledger-header duplication as report-rollup. The receipt boundary rules are subtle enough that a weaker scheduled model could plausibly re-derive them wrong — they're specified in prose with no executable check. No model recommendation for what is a recurring, headless, cost-sensitive job.
- *Improvements:* Same shared helper as report-rollup (window math + ledger append, pytest-covered, planted violations per clean-code-architecture-guards). Add "Sonnet-class" to the skill text. Cross-link report-receipt as the upstream producer so receipt-quality issues get fixed at the source.

### unreal-reset-build-env

**What it does.** Resets a Windows Unreal build shell before a fresh build via a bundled PowerShell helper: stops process trees seeded by Build.bat/RunUAT/UBT/UAT/UBA/MSBuild nodes, clears Visual Studio/MSBuild/.NET/UAT/`uebp_*` environment variables, sets `MSBUILDDISABLENODEREUSE=1` — while deliberately preserving Perforce variables and leaving the editor alive unless told otherwise.

**When to use.** Before starting any fresh Unreal build on Windows, especially after a failed or interrupted build left workers, MSBuild nodes, or poisoned env vars behind.

**Parameters** (script flags):

| Flag | Use |
|---|---|
| `-Root <path>` | Scope to one Unreal root — prefer whenever possible |
| `-AllWorkspaces` | All roots; only when the user asks for all build activity |
| `-IncludeEditor` | Also stop editor/game processes (off by default — unsaved work) |
| `-SkipProcessStop` / `-SkipEnvironmentCleanup` | Run only half the job |
| `-WhatIf` | Preview without changing anything |

**Examples.**
- Claude: `Use @skill unreal-reset-build-env on D:\p4\ss-5.8\root — preview with -WhatIf first.`
- Codex: `@skill unreal-reset-build-env — clean the build shell for <root>, processes and env.`
- Copilot: attach the SKILL.md → "Run the helper with -Root <path> -WhatIf and show me what it would stop."

**Architect's review.**
- *Strengths:* Safe-by-default design: Perforce state preserved, editor untouched without `-IncludeEditor`, `-WhatIf` offered for shared machines. The Common Mistakes section names the real footgun — running the cleaner in a child shell cleans the *child's* environment, accomplishing nothing. Delegating enumeration to a script is correct; process-tree walking is exactly what prose instructions get wrong.
- *Weaknesses:* The bundled `scripts\Stop-UnrealBuildAndCleanEnv.ps1` now ships with the skill, but the Quick Start hard-codes `D:\git\worky\...`, which fails on the `C:\git\worky` machine — harness-setup.md explicitly warns paths must resolve per machine.
- *Improvements:* Replace the hard-coded skill path with the `<skill base dir>` convention its sibling skills already use. Add a post-run verification one-liner (list surviving Unreal/MSBuild processes) so "clean" is evidence, not assumption.

### unreal-ugs-release

**What it does.** The full operating guide for UnrealGameSync precompiled editor binaries: default VisTest profile, required workflow (validate `ZippedBinariesPath` → clean shell → build editor + ShaderCompileWorker → BuildGraph `-p4 -NoSubmit` → validate zip/version/BuildId/worker hashes → manual editor launch → only then `-p4 -submit`), the successful BuildGraph command shape, a concrete validation-evidence checklist, and troubleshooting boundaries. Paired with the human copy/paste runbook at `runbooks\ugs-pcb\UGS_PCB_Runbook.md` under an explicit both-or-neither sync rule.

**When to use.** Building, validating, submitting, troubleshooting, or updating UGS PCB archives and the Submit-To-Perforce-For-UGS flow.

**Parameters.** No formal arguments — a Default Profile table (workspace, root, uproject, editor target, archive stream, expected version, P4 stream/client) that the user can override per project.

**Examples.**
- Claude: `Use @skill unreal-ugs-release — build and validate a fresh VisTest PCB, no-submit first.`
- Codex: `@skill unreal-ugs-release: troubleshoot missing modules in a clean UGS consumer sync.`
- Copilot: attach the SKILL.md → "Follow the Required Workflow through the no-submit validation and stop before submit."

**Architect's review.**
- *Strengths:* This is evidence-based operations at its best — the Validation Evidence list converts "it should be ready" into fifteen checkable facts (version, single BuildId, worker hashes, digest match, clean consumer launch). The wrong-archive-name trap (`main-content` stream producing a valid-looking zip at the wrong depot path) is documented twice because it's the expensive failure, and the troubleshooting boundaries stop scope creep ("post-launch tool crashes are separate investigations").
- *Weaknesses:* Hard-codes `D:\git\worky\...` for the runbook path — on the C: machine the very first instruction ("read this first") points at a file that isn't there. VisTest constants live inside a nominally general skill; the profile table mitigates but drift is one edit away. It's the longest skill in the set and mandates also reading the runbook, so every invocation pays a double token toll even for a narrow question. The skill↔runbook sync rule is enforced by discipline alone — the exact "rule in prose" failure mode clean-code-architecture-guards exists to prevent.
- *Improvements:* Resolve the runbook as `<skill base dir>\..\..\runbooks\ugs-pcb\` (portable across both machines). Split deep troubleshooting into `references/troubleshooting.md`, loaded on demand — progressive disclosure would cut routine-invocation cost substantially. Move the VisTest profile into a small data block (or per-project file) so project onboarding is additive. Add a mechanical sync check between runbook and skill command shapes, even a crude one.

### update-claude-pricing-doc

**What it does.** Refreshes `output\claude-pricing.json` — the cached per-model USD rates that report-receipt prices sessions with — by invoking the `claude-api` skill and extracting `input`/`output` rates per model. Fixed JSON shape; cache multipliers (0.1× read, 1.25× write) live in a note and are derived inline by the consumer.

**When to use.** When report-receipt prints its ⚠️ staleness warning (pricing >7 days old), when Anthropic changes pricing, or when the output file is missing. Cache verified present and fresh as of 2026-07-12.

**Parameters.** None.

**Examples.**
- Claude: `/update-claude-pricing-doc` — per the skill, run it on a Haiku session; it's a table-read + JSON-write.
- Codex: not runnable as written — see review.
- Copilot: not runnable as written — see review.

**Architect's review.**
- *Strengths:* Textbook token-cost engineering: caching seven numbers means every receipt skips loading the full claude-api reference bundle, and the explicit "use Haiku — needs no reasoning" line is the model-selection discipline more skills should copy. Tight output contract (exact JSON shape, exact confirmation line), and the staleness protocol pairs cleanly with the consumer's warning.
- *Weaknesses:* The "When to Run" section cites `Agent/skills/output/claude-pricing.json` — a path that doesn't exist (missing the `update-claude-pricing-doc` segment); a literal-minded model would conclude the file is always absent and refresh every time. Harness-locked by its data source: `claude-api` is a Claude Code bundled skill, so Codex/Copilot cannot execute this even though the file it maintains is harness-neutral. Refresh is purely pull-based — nothing schedules it.
- *Improvements:* Fix the path typo (one line). Add a documented fallback source (docs URL) so other harnesses can refresh the cache. Either add it to the scheduler or let report-receipt auto-run it when stale instead of just warning.

### update-model-routing

**What it does.** Checks centralized `model-routing.json` staleness deterministically and refreshes model IDs only from the official OpenAI and Anthropic sources when required.

**When to use.** When model-routing data may be stale, exact Codex or Claude IDs need verification, or a plan needs current routing profiles.

**Parameters.** None. The checker reads `model-routing.json` and reports `CURRENT` or `STALE`.

**Examples.**
- Claude: `@skill update-model-routing — check whether model-routing.json is current.`
- Codex: `@skill update-model-routing — verify the routing reference before planning.`
- Copilot: attach `Agent\skills\update-model-routing\SKILL.md` → "Check model-routing.json and refresh it only if stale."

> Review pending — rerun with "review".

### update-skills-readme

**What it does.** Regenerates this documentation pair from the skill set: traverses `Agent\skills\*\SKILL.md`, rebuilds `README.md` (inventory, per-skill usage, parameters, examples, call formats, TOC), and renders `README.html` via `scripts/render_html.py` (uv-run, self-contained deps). By default it preserves each skill's existing *Architect's review* block verbatim; with the `review` argument it re-evaluates them.

**When to use.** After adding, removing, or meaningfully editing any skill. Pair the edit and the doc regeneration in the same change, like the ugs skill↔runbook sync rule.

**Parameters.** Optional: `review` — also regenerate the Architect's review sections (needs a frontier-class model; without it, reviews are preserved and only factual sections update).

**Examples.**
- Claude: `/update-skills-readme` · `/update-skills-readme review`
- Codex: `@skill update-skills-readme — I added a new skill, update the docs.`
- Copilot: attach the SKILL.md → "Regenerate README.md and README.html from the current skill directories."

**Architect's review.**
- *Strengths:* Separating mechanical regeneration (default) from judgment regeneration (`review`) matches cost to need — inventory updates run on a cheap model, reviews only pay for reasoning when asked. HTML is derived output from a committed script, not hand-maintained. The generation pipeline was exercised at creation time (this document is its output), so the HTML path is proven, not aspirational.
- *Weaknesses:* New and unproven beyond first generation. It's another manual sync rule — nothing *forces* a skill edit to trigger regeneration, so this README can silently drift stale (same class of problem as the ugs pair). Review preservation keys off the `**Architect's review.**` heading structure; a future format change breaks the preserve-vs-regenerate split.
- *Improvements:* Add a cheap freshness check a session can run (compare newest SKILL.md mtime against README generation date; warn on drift). Consider a repo guard per clean-code-architecture-guards once the vault gains a test harness.

---

## Architect's overview

### Harness coverage matrix

Discovery on this machine, verified 2026-07-12: Claude junction ✅ · Codex junction ✅ · Copilot ❌ (adapter TBD — every skill is manual-attach only until `harness-setup.md` § Copilot is filled in).

| Skill | Claude | Codex | Copilot | Notes |
|---|---|---|---|---|
| agent-plan | ✅ | ✅ | 📎 | Uses centralized routing profiles |
| agent-preflight | ✅ | ✅ | ⚠️ | Codex checks defined; Copilot sections are placeholders |
| clean-code-architecture-guards | ✅ | ✅ | 📎 | Content fully portable |
| clean-code-error-handling | ✅ | ✅ | 📎 | Language-agnostic design and refactoring workflow |
| python-quality-gate | ✅ | ✅ | 📎 | Carries ugs-project baggage |
| python-tdd-cycle | ✅ ⚠️ | ✅ | 📎 | ⚠️ unstated overlap with superpowers TDD on Claude |
| ready-player-one | ✅ | ✅ | 📎 | Alias → agent-preflight |
| report-receipt | ✅ | ✅ | ⚠️ | Copilot: model rec only, no cost recipe |
| report-rollup | ✅ | ✅ | 📎 | Portable |
| report-status | ✅ | ✅ | 📎 | Portable |
| unreal-reset-build-env | ✅ | ✅ | 📎 | Bundled Windows PowerShell helper |
| unreal-ugs-release | ⚠️ | ⚠️ | 📎 | D:\ runbook path breaks the C:\ machine |
| update-claude-pricing-doc | ✅ | ❌ | ❌ | Data source is a Claude-bundled skill |
| update-model-routing | ✅ | ✅ | 📎 | Uses official provider sources when stale |
| update-skills-readme | ✅ | ✅ | 📎 | HTML step needs uv on PATH |

✅ works as written · ⚠️ partial / caveat · ❌ blocked · 📎 reachable only by manually attaching SKILL.md

### Skill gaps

1. **Copilot adapter** — the whole third leg is TBD in `harness-setup.md`. Until a `.github/copilot-instructions.md` (or equivalent) points at AGENTS.md and the skills tree, Copilot coverage is a per-prompt manual exercise.
2. **Process skills outside Claude** — TDD-enforcement, code review, brainstorming, and branch-finishing discipline come from the superpowers plugin, which exists only on the Claude side. A Codex session gets python-tdd-cycle and nothing else; there is no cross-harness equivalent of verification-before-completion, which is the one that most changes outcomes.
3. **Partial skill self-verification** — the README sync guard now has coverage, but the remaining manual rules (ugs skill↔runbook, window math, filename conventions) still lack machine checks. A small pytest harness over `Agent\` could validate referenced paths and ledger headers before they drift.
4. **No commit/PR skill** — AGENTS.md carries git-safety rules and the harness prompt carries trailer conventions, but no vault skill encodes "how work lands" for harnesses that lack built-in git workflow guidance.
5. **Codex pricing cache** — report-receipt must fetch OpenAI pricing live (or report N/A) every time; there's no `codex-pricing.json` counterpart to the Claude cache.
6. **Scheduler operations** — report generation is scheduled (registration is machine-local per commit 9e426da), but there's no runbook/skill for triaging a missed or failed scheduled run: where logs land, how to re-register, how to backfill (the window-override parameter exists; the procedure around it is undocumented).

### Token-costly mistakes

Ranked by observed or expected cost, each with its fix:

1. **Parsing session transcripts through the context window.** report-receipt's cost analysis reads the whole `.jsonl` to sum four fields; on long sessions that's megabytes of input tokens for arithmetic. *Fix:* a stdlib summing script (see its review) — the single highest-leverage change available.
2. **Running mechanical skills on frontier models.** Pricing refresh, preflight checklists, and env cleanup need no reasoning. The skills that say so (update-claude-pricing-doc: Haiku; agent-preflight: Haiku/o4-mini) are the pattern; the report generators should say so too. *Fix:* honor the inventory table's model column.
3. **Loading the full claude-api bundle when the pricing cache would do.** The cache exists precisely to avoid this. *Fix:* trust `claude-pricing.json` unless the staleness warning fires; fix the path typo that could trick a model into always refreshing.
4. **The ugs double-read.** Every unreal-ugs-release invocation loads the longest skill *plus* its runbook, even for one troubleshooting question. *Fix:* progressive disclosure — split troubleshooting into on-demand references.
5. **Mid-session model switches.** Switching models invalidates the prompt cache; report-receipt documents that the switch can cost more than staying on the pricier model. *Fix:* pick the model before the session, not during.
6. **Idle gaps past the 5-minute cache TTL (Claude).** Each idle-then-resume rewrites the full context as cache-write tokens at 1.25× input rate. *Fix:* batch prompts; don't leave a loaded session simmering.
7. **Re-reading loaded guidance to "confirm" it.** AGENTS.md bans re-reading itself to answer "is this loaded" — the revision date from memory is the answer. The same applies to re-reading SKILL.md files already in context.
8. **Preflight dead-ends in autonomous runs.** A NOT-READY verdict whose remediation the agent is forbidden to perform (agent-preflight Check 2, observed 2026-07-12) burns a session doing nothing. *Fix:* mark human-only remediations as such and let inherited settings satisfy the check.
9. **Hard-coded per-machine paths.** Every `D:\git\worky\...` literal is a failed command, an error message, and a retry loop on the C: machine. *Fix:* the `<skill base dir>` relative-path convention the report skills already use.

## Maintaining this document

- **Source of truth:** this file. `README.html` is rendered output — never edit it directly.
- **Regenerate:** `/update-skills-readme` (Claude) or `@skill update-skills-readme` (Codex) after any skill add/remove/edit. Factual sections are rebuilt; Architect's review blocks are preserved verbatim unless you pass `review`.
- **HTML only:** `uv run Agent/skills/update-skills-readme/scripts/render_html.py` regenerates `README.html` from this file.
- **Review refresh:** `/update-skills-readme review` — run it on a frontier-class model; reviews are judgment, not transcription.
- **Convention:** treat "skill changed, README untouched" as an unfinished change, the same way the ugs pair treats skill↔runbook drift.
