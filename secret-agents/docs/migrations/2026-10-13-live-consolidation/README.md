# Live Agent Consolidation — 2026-10-13

The earlier content migrations deferred machine adapters and automation. This follow-up completes that scope on this machine: the active source is `handbag-of-holding/secret-agents`, and Worky remains the report/project data vault.

## Applied changes

- `~/.agents/root` contains the local handbag-of-holding vault path.
- `~/AGENTS.md`, `~/.agents/AGENTS.md`, `~/.codex/AGENTS.md`, `~/.claude/AGENTS.md`, `~/.claude/CLAUDE.md`, and `~/.copilot/copilot-instructions.md` are symlinks to canonical guidance.
- `.agents/skills`, `.codex/skills`, `.claude/skills`, and `.copilot/skills` are real directories. Each has 52 links to the matching canonical or generated-alias directory: 208 links total. Existing Codex system skills and harness plugins are preserved.
- The original report runner, found under `C:/git/old-obsidian/worky/Scripts`, is recovered as `scripts/run_report.py`. Its data-vault selection is explicit/environment/sibling; successful runs in a synced non-Git vault update the dashboard without attempting Git commits. It never commits into a parent repository.
- Windows tasks `worky-status-report` and `worky-monthly-rollup` now invoke that runner with the current Worky path. Triggers, principals, and settings were compared before/after and preserved. No task was manually started and no model-backed report was generated.
- The recovery verifier always checks the archives and current consolidated content. Comparing original checkout bytes is optional via `--original-checkout`; it no longer requires the old `C:/git/handbag-of-holding` path. Verified-source counts reflect successful comparisons rather than merely counted manifest entries.

## Preservation

- [Before-machine snapshot](before-machine.json): original bootstrap text and adapter targets.
- `worky-status-report.before.xml` and `worky-monthly-rollup.before.xml`: original task definitions; matching `.after.xml` files record the migrated actions.
- [Original runner](run_report.py.original): unmodified source, SHA-256 `29edc43088effd459600b61e7dcad757ab4dd715b6455cc28f68354013354a0b`.
- The two earlier migration archives and retired snapshots remain unchanged. All 118 recovery-source files also matched the relocated archived checkout at `C:/git/old-obsidian/handbag-of-holding`.
- Retired checkouts and history are retained as recovery evidence, never active adapter targets. No Worky report or project data was moved or deleted.

## Validation

The initial suite had 168 passing tests. New regression checks cover explicit/environment/sibling data-vault selection, no-write validation, missing vaults, non-Git vaults, avoidance of parent-repository commits, self-contained preservation verification, missing optional checkouts, and archive corruption. New behavior was observed failing before the implementation changes; archive-corruption checks prove the retained preservation gate.

Both runner modes pass `--check` against the live Worky vault. This verifies paths and command selection, not a model-generated report. [Adapter verification](adapter-verification.json) records the checked link counts. The full gate passed: 34 files type-checked and linted/formatted, 178 tests passed. The harness CLI check, catalog check, and archive audit passed. Final gate and integration results are in [verification.json](verification.json).

Independent review confirmed the live links, task definitions, original runner hash, and retained archive checks. Its dependency finding was addressed by declaring and locking PyYAML. The old whole-directory Claude migration instructions are explicitly superseded to prevent another machine from following them.

The recovered runner retains its preexisting success/skip detection and report-commit behavior for actual Git vaults; redesigning those behaviors was outside this relocation. The current Worky vault is not a Git repository, so its runs do not stage or commit data. No approval/trust settings or foreign-pack versions were changed.

Existing sessions may retain their startup skill snapshot; restart them to refresh the skill picker. Filesystem wiring is already live. Other machines require their own local adapter reconciliation against their synced vault path.
