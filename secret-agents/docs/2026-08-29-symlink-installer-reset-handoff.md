## Work Receipt

### Goal
- Stop the current installer redesign and preserve a clear restart point for a much smaller product: create the symlinks needed to use the canonical instructions and skills, or report why that cannot be done.
- Identify behavior and tests worth salvaging without carrying forward planning, receipts, backup workflows, uninstall machinery, type dispatch, or sprawling error handling.

### Changes
- Reviewed PR #5, its local spec and plan, and the PR-head implementation in the separate installer-redesign worktree.
- Rejected the current architecture as a basis for further work: it replaces enum dispatch with `isinstance`, retains a generic nullable compensation record, and distributes variant interpretation across executor, planning, receipts, and CLI modules.
- Defined a simpler target and a salvage/discard recommendation below. No production code, branch, PR, or existing document was changed as part of this handoff.

### Files / Systems
- Primary checkout: `C:\git\handbag-of-holding`, branch `batch-3-rollback-execution-and-cli`; it has pre-existing user changes that must be preserved.
- PR-head worktree: `C:\git\handbag-of-holding-installer-redesign`, branch `batch-3-installer-domain-cli-redesign`, currently at PR #5 head `872c120`.
- Current design documents: `secret-agents/docs/superpowers/specs/2026-08-29-installer-domain-and-cli-design.md` and `secret-agents/docs/superpowers/plans/2026-08-29-installer-domain-and-cli-redesign.md`. They were removed from tracked history by `1574b73` and now survive as ignored local files.
- Main implementation under review: `secret-agents/src/secret_agents_setup/`, especially `executor.py`, `planning.py`, `receipts.py`, `cli.py`, `links.py`, `harness_profiles.py`, `catalog.py`, and `root.py`.
- Existing unrelated working-tree changes: `secret-agents/AGENTS.md`, skills README files, `skills/python-quality-gate/SKILL.md`, and `src/secret_agents_setup.egg-info/`. Do not modify, stage, discard, or attribute these to the installer reset.

### Technical Decisions
- The product requirement is not a transactional package manager. It is: make the instruction and skill links needed by the selected harnesses, or refuse with a useful reason.
- Do not overwrite, move, or back up an existing path. A correct existing link is unchanged; any conflicting path blocks the invocation before mutation. Because user content is never displaced, receipts and backup restoration are unnecessary.
- Remove uninstall from scope. If uninstall is ever requested later, design it from the actual requirement rather than retaining receipts preemptively.
- Remove persistent plans, status/change unions, execution-result hierarchies, compensation kind enums, and receipt schemas. Validation before mutation may remain ordinary private control flow inside one install operation; it does not need a public `Plan` model.
- Use a small state-owning `Installer` class. This is not a god object because its scope is one narrow workflow. Its interface should be approximately `install(harnesses) -> InstallSummary`; its constructor owns the canonical root, home, and link adapter.
- Use one link value containing only `source` and `destination`. The link adapter can inspect the canonical source to create the correct file or directory symlink; no `kind`, `is_directory`, `is_skills`, or `isinstance` dispatch is needed.
- Always preserve existing harness skill directories. Create one symlink per canonical skill inside the harness skill directory rather than replacing the whole directory. This permits third-party skills to coexist. Deduplicate shared destinations such as `.agents/skills` before mutation.
- Before creating anything, resolve the complete desired link set and reject every conflict. During creation, keep only an in-memory list of links and empty parent directories created by this invocation. On failure or cancellation, remove those new paths in reverse order. This is a small local cleanup invariant, not a general transaction framework.
- Keep error handling at one seam. `Installer.install` may raise a small `InstallError` family for conflict, unavailable symlink capability, and creation failure. The CLI catches it once, prints one diagnostic, and returns one nonzero exit code. Programmer errors and cancellation are not reformatted.
- Add a production-source architecture guard that rejects `isinstance`, type/kind dispatch, and an empty scan. It must include a planted violation. Use size/complexity checks only as review tripwires, not automatic split rules.

### Coordination
- Recommended salvage:
  - Keep root discovery and canonical skill enumeration behavior from `root.py` and `catalog.py`, but simplify their interfaces and error types if they remain hard to read.
  - Keep the harness destination facts from `harness_profiles.py`; discard `_MappingSpec.is_skills`, mapping unions, and factory indirection. A small immutable `HarnessLayout` table is sufficient.
  - Keep the cross-platform OS knowledge and focused creation/verification tests from `links.py` and `tests/test_links.py`. Rewrite the adapter if retaining its current error machinery costs more than the platform behavior is worth.
  - Keep acceptance expectations for destination paths, coexistence with third-party skills, idempotent correct links, conflict refusal, and Windows capability failure.
  - Salvage the behavioral lesson from commits `9db131d` and `d665d8e`: a failed link creation must not leave a partial link, and cleanup failure must not hide the original failure. Implement that contract simply in the link adapter.
  - Salvage cancellation cleanup from `8a6d691` only in the reduced in-memory form: remove paths created by the current invocation, then re-raise the original cancellation.
- Recommended discard/rewrite:
  - `planning.py`, `receipts.py`, `executor.py`, their error modules, and most tests coupled to plans, receipts, journals, rollback record shapes, typed change unions, backup restoration, or uninstall.
  - Backup-path work from `7a5f53f` and managed-home uninstall containment from `059cb77`; those solve features that are removed by the simplified scope.
  - The current `cli.py` orchestration and `_Session`; retain only command-line spelling that the user still wants.
  - Tasks 5–14 of the current plan. Do not continue implementing that plan.
- Do not cherry-pick the architectural commits merely because their tests pass. Extract behavioral tests or small platform facts deliberately into a new branch after the replacement interface is approved.

### Risks / Unknowns
- Confirm whether a separate `check` command is valuable. Recommendation: start with only `install`; its summary already reports created and unchanged links.
- Confirm whether instruction links should be installed alongside skill links. Current behavior links canonical `AGENTS.md` to each harness instruction location; the simplified design assumes that remains desired.
- Confirm that no released user depends on receipt-based uninstall or automatic conflict backups. PR #5 is open and not merged, but external use of an earlier branch/script should be checked before deleting compatibility code.
- On Windows, symlink creation may require Developer Mode or elevated privilege. The adapter must refuse clearly; it must not introduce copy, junction, or hard-link fallbacks unless explicitly requested later.
- Preflight eliminates known conflicts but cannot eliminate races between validation and creation. Use exclusive link creation and stop on the first race; clean only paths created by this invocation.

### Handoff
- Use the following prompt in a fresh session. It intentionally asks for a short design before any implementation:

```text
Resume the symlink-installer simplification in C:\git\handbag-of-holding.

Read first:
- secret-agents/docs/2026-08-29-symlink-installer-reset-handoff.md
- secret-agents/AGENTS.md
- the current root.py, catalog.py, harness_profiles.py, links.py, and their tests

Do not execute the old installer-domain-and-CLI redesign plan. Do not edit code yet.
Preserve all unrelated dirty-worktree changes. Inspect both worktrees and PR #5 read-only.

Product requirement:
Create the symlinks needed to use the canonical AGENTS.md and canonical skills in the selected harnesses, or report why it cannot be done. Never overwrite or move existing content. Existing correct links are unchanged; conflicts block before mutation. Preserve third-party skills by linking canonical skills individually into real harness skill directories.

Rejected scope:
- receipts or persistent installation state
- backups or restoration
- uninstall
- public plan/status/change models
- generic transaction or compensation frameworks
- isinstance, type/kind dispatch, nullable payload bags, or session/context bags
- copy, junction, or hard-link fallback

Design a small OO implementation around a state-owning Installer and a cross-platform link adapter. Show:
1. the exact class interfaces and constructors;
2. state ownership and dependency direction;
3. the install algorithm, including preflight and cleanup of only this invocation's paths;
4. the minimal error contract;
5. which existing source files and behavioral tests will be retained, rewritten, or deleted.

Apply the deletion test to every proposed module. Prefer one deep Installer interface over many shallow types. Do not produce a large implementation plan and do not write code. Stop for human approval of the class design.
```

### Suggested Status Bullet
- Stopped PR #5's overbuilt installer redesign and captured a restart design for a minimal, conflict-refusing symlink installer with no receipts, backups, uninstall, public planning model, or runtime type dispatch.

### Efficiency Analysis

##### Actual Prompt
- "I am reviewing [rhyolyn/handbag-of-holding#5](https://github.com/rhyolyn/handbag-of-holding/pull/5) and it's so poorly written I don't know what to do next. As an example C:\git\handbag-of-holding\secret-agents\src\secret_agents_setup\executor.py is a mess of long functions and other smells like huge if/else blocks and isinstance checks. isinstance should never appear in my code bases. It indicates a total design failure. This is the plan C:\git\handbag-of-holding\secret-agents\docs\superpowers\plans\2026-08-29-installer-domain-and-cli-redesign.md. Is this and other smelly files going to improve or should 'i give up now."

##### 20/20 Hindsight Corrected Prompt
- "Review PR #5 and the referenced spec/plan without editing. Determine whether the remaining plan removes long workflows, type/kind dispatch, generic nullable records, and unjustified avoidance of state-owning classes. My actual product requirement is only to create the instruction and skill symlinks or report a conflict; receipts, backups, uninstall, and a public planning model are not requirements. Recommend what behavioral work is salvageable and whether the architecture should be discarded."

#### AI Cost Analysis
- Model: `gpt-5.6-sol`. Cumulative Codex usage at handoff creation: 2,745,620 input tokens, of which 2,618,624 were cached; 126,996 were uncached input; 22,210 were output. Reasoning output was 14,274, a diagnostic subset of output rather than an additional billed category. Total consumption was 2,767,830 tokens.
- Approximately 95% of input tokens were cached. The large total came from the long inherited instruction context, full reads of the 1,228-line plan, spec, executor and related files, two parallel review reports, and several follow-up turns correcting the initial framing.
- Subscription/rate-limit consumption is distinct from token count. Dollar/API-equivalent value is `N/A`: `gpt-5.6-sol` is an internal Codex model alias without an unambiguous authoritative public API rate. If this session is covered by an included subscription, marginal dollar cost is $0.
- Avoidable spend in this review: the assistant initially framed the failure as asking AI to "improve code," causing multiple corrective turns even though the user had provided concrete smells and constraints. The first answer should have identified immediately that the plan itself mandated `isinstance` and preserved the unwanted architecture.

#### Human Improvement Plan
- Previous receipt advice said to approve naming and module design before implementation and recorded a hard gate of "no code until the user approves the design." That gate was not honored by the subsequent execution workflow: implementation continued while the spec still said `Awaiting written-spec review`.
- No additional prompt detail from the user would have repaired the current plan; the user's original review named the concrete failures. The effective intervention is a mandatory design-only stop plus machine-enforced architectural rules, not a longer implementation prompt.
- The fastest recovery is one fresh design session using the handoff above, followed by one implementation seam per session. Do not carry the 1,228-line rejected plan into future implementation context.
- Standing habits: state the smallest product requirement before discussing architecture; require explicit state ownership and class interfaces before code; convert absolute rules such as "no isinstance" into CI guards with planted violations.
