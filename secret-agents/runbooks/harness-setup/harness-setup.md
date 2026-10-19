# Harness Setup Runbook

How to wire a machine and its harnesses to the canonical agent guidance and skills in this vault. Rewritten 2026-08-30 for the `handbag-of-holding` consolidation; design rationale in `docs/specs/2026-08-30-ready-player-one-design.md`. The always-on per-session rules (skill fallback, runbook lookup, symlink-not-copy) stay in `AGENTS.md` § Environment & Harness Adapters.

Run `/ready-player-one` after any step here — it verifies this layout and autofixes safe gaps.

## Principles

- The vault (`handbag-of-holding`, an Obsidian vault) lives at `~/obsidian/handbag-of-holding` on every OS. `<agent-root>` defaults to its `secret-agents` directory, identified by `.agent-root.json`; canonical skills live at `<agent-root>/skills/<collection>/<canonical-name>`. Obsidian Sync is authoritative across machines.
- The vault contains **only skills we author**. Foreign packs (superpowers, mattpocock-skills, …) are installed per machine via each pack's official mechanism — never copied into the vault, never linked from inside the vault (Obsidian sync flattens links into copies on other machines).
- Harness files are adapters pointing back at `<agent-root>`. Never copy shared guidance or skills where a link will work.
- **Mixing directories** are real directories containing per-skill links, including Claude's directory. Never make a mixing directory a whole-dir junction into the vault: third-party installers writing to that path would write through into the vault.
- Prefer open-standard names (`AGENTS.md`, top-level `SKILL.md`) so content stays portable across harnesses.
- When adding a harness, add its adapter rules below instead of forking content.

## Per-machine bootstrap (new machine, in order)

1. Sync the vault to `~/obsidian/handbag-of-holding`. Keep the lowercase `obsidian` spelling on case-sensitive filesystems.
2. Resolve and validate `<agent-root>` using the path contract below. No `~/.agents/root` pointer is needed; old pointer files are ignored by source discovery.
3. Create the adapter links for each harness installed on this machine (tables below) — or just run `/ready-player-one` in any working harness and let autofix create them.
4. Install foreign packs via their official mechanisms (commands in `secret-agents\packs.json`), including the pack's in-progress skills we rely on.
5. Set permissions/trust per harness (below).
6. Run `update-agent-stack` once to seed `~/.agents/versions.json`.
7. Run `/ready-player-one` until the verdict is `ready`.

## Source path contract

| OS | Default authored skills source |
|---|---|
| Windows | `%USERPROFILE%\obsidian\handbag-of-holding\secret-agents\skills` |
| macOS | `$HOME/obsidian/handbag-of-holding/secret-agents/skills` |
| Linux | `$HOME/obsidian/handbag-of-holding/secret-agents/skills` |

Python uses `Path.home()` and path components, PowerShell uses `$HOME` with `Join-Path`, and Bash/zsh uses `$HOME` with `/`. Never copy a particular user's absolute path to another machine. Quote expanded paths so home directories containing spaces work. Expand a leading `~` in explicit overrides; prefer an absolute `SECRET_AGENTS_ROOT` in shell configuration.

The shared stdlib resolver is `src/secret_agents_setup/paths.py:agent_root_path`. Precedence is an explicit source argument, then `SECRET_AGENTS_ROOT`, then the home-relative default. `SECRET_AGENTS_ROOT` names `secret-agents`, not its `skills` subdirectory. The installer validates the root marker and required entries. Missing or invalid sources fail explicitly; cwd, script ancestry, harness discovery paths, and legacy pointer files never supply a fallback.

Catalog `--skills-root`, renderer `--readme`/`--skills-root`, and routing checker `--reference` select explicit inputs for development or alternate checkouts. `install-skills --target` is a destination flag and does not change its source. Keep installed skill slots pointing only to their matching `<agent-root>/skills/_generated/<canonical-name>` projection directory.

Resolve the default and inspect the catalog from any working directory:

```powershell
$AgentRoot = Join-Path $HOME 'obsidian/handbag-of-holding/secret-agents'
python (Join-Path $AgentRoot 'skills/skill-authoring/query-all-skills/scripts/catalog.py') check
```

```bash
AGENT_ROOT="$HOME/obsidian/handbag-of-holding/secret-agents"
python3 "$AGENT_ROOT/skills/skill-authoring/query-all-skills/scripts/catalog.py" check
```

Use `/install-skills --update` to install authored skills from this source. Keep foreign packs in their official harness-managed locations; do not vendor them into the authored library. The legacy `harness_setup.py` CLI also uses this source default; its installation-layout limitation is documented below.

## Adapter layout

`<root>` below = `~/obsidian/handbag-of-holding`; `<agent-root>` = `<root>/secret-agents`, unless explicitly overridden above. On Windows, per-skill directory junctions are supported by the installer; file adapters are symbolic links. On macOS/Linux use symlinks. No copied guidance or skill bodies.

### Shared (all harnesses)

| Path | Kind | Target |
|------|------|--------|
| `~/.agents/skills/<canonical-name>` | per-skill directory link (real parent dir) | `<agent-root>/skills/_generated/<canonical-name>` |
| `~/AGENTS.md`, `~/.agents/AGENTS.md` | file symlinks | `<agent-root>/AGENTS.md` |

`~/.agents/skills` is the path most likely to be targeted by cross-harness installers (`npx skills`, etc.) — it must be a real directory so those installs land beside our links instead of inside the vault.

### Claude Code

| Path | Kind | Target |
|------|------|--------|
| `~/.claude/AGENTS.md` | file symlink | `<agent-root>/AGENTS.md` |
| `~/.claude/CLAUDE.md` | native instruction file symlink | `<agent-root>/AGENTS.md` |
| `~/.claude/skills/<canonical-name>` | per-skill directory link (real parent dir) | `<agent-root>/skills/_generated/<canonical-name>` |

Claude's plugins remain installed through its plugin system; the real skills directory also permits foreign entries to coexist safely.

Foreign packs: `/plugin install superpowers` (claude-plugins-official), `/plugin install mattpocock-skills` (mattpocock marketplace, already registered in settings).

Permissions: `permissions.defaultMode` = `dontAsk` (or `bypassPermissions`) in **both** `~/.claude/settings.json` and the project's `.claude/settings.json` — agents spawned in worktrees fall back to global.

New/changed skills register at **session start**; a skill added mid-session needs a fresh session (ready-player-one can read it into the current session as a stopgap).

### Codex

| Path | Kind | Target |
|------|------|--------|
| `~/.codex/AGENTS.md` | file symlink | `<agent-root>/AGENTS.md` |
| `~/.agents/skills/<canonical-name>` | current user discovery, per-skill directory link | `<agent-root>/skills/_generated/<canonical-name>` |
| `~/.codex/skills/<canonical-name>` | compatibility per-skill directory link | `<agent-root>/skills/_generated/<canonical-name>` |

Current [Codex documentation](https://learn.chatgpt.com/docs/build-skills#where-codex-loads-local-skills) names `~/.agents/skills` for user discovery and supports linked skill folders. Preserve Codex's `.system` directory when maintaining compatibility links.

Foreign packs: superpowers via `/plugins` → search → install; mattpocock-skills via `npx skills@latest add mattpocock/skills`.

Trust: `[projects.'<project path>'] trust_level = "trusted"` in `~/.codex/config.toml` per project.

### Copilot

The repository's harness profile projects shared skills through `~/.agents/skills` and guidance through `~/.copilot/copilot-instructions.md`. The installer also maintains compatibility per-skill links in `~/.copilot/skills`. Live model invocation is separate from checking these filesystem projections. Foreign packs remain official installations.

## Historical one-time migration from `worky\Agent` (2026-08)

The former canonical root `C:\git\worky\Agent` (and `D:\git\worky\Agent`) is archived by the user and must not be referenced by any link. **The numbered steps below are historical and superseded; do not execute them.** Use the current adapter tables and `install-skills` procedure above when reconciling another machine. In August, the procedure was:

1. Repoint `~/.claude/skills` junction → `<agent-root>/skills`.
2. Replace the `~/.agents/skills` junction with a real dir + per-skill links (per the shared table).
3. Recreate `~/.codex/skills` per-skill links against `<agent-root>/skills` (the old set covered only a fraction of the skills).
4. Do **not** migrate skill files from worky: our skills already live in this repo under their current (renamed) names; everything else there was an accidental write-through copy of mattpocock-skills — superseded by official installs.
5. Run `/ready-player-one`.

## Verifying an adapter

Ask the agent: "what revision of the shared guidance is loaded?" A correct revision date from `AGENTS.md` proves the instruction link works; a wrong or missing answer means the link is broken on this harness — recreate it per the tables above, then ask for a full re-read. For skills, `/ready-player-one`'s session-diff is the authoritative probe.

## October vault recovery

The current vault is `~/obsidian/handbag-of-holding`; resolve its local path through the home-directory convention above on each machine. The initial October migration deferred live adapters. The [completed local cutover](../../docs/migrations/2026-10-13-live-consolidation/README.md) replaced those adapters, installed all 52 authored skill names, and migrated reporting task actions. The August migration section is historical; the three retained Worky checkin workflows are authored skills, not foreign packs.

## Scheduled Worky reporting

The executable source is `<agent-root>/scripts/run_report.py`. Worky contains data and run logs. The runner resolves data from `--vault`, then `WORKY_VAULT_ROOT`, then the sibling `worky` vault. For a synced vault without Git metadata, successful reports update the dashboard without attempting a commit. A vault that is itself a Git repository retains commit-on-success behavior.

Check both modes without generating reports:

```powershell
python <agent-root>/scripts/run_report.py status --check
python <agent-root>/scripts/run_report.py monthly --check
```

Windows tasks `worky-status-report` and `worky-monthly-rollup` invoke that file with an explicit `--vault` and Worky as the working directory. Changing task actions must preserve triggers, principals, and settings. `--dry-run` still invokes Claude and writes report output; use `--check` for validation only.

The legacy `harness_setup.py install` CLI accepts whole-directory projections when a skills directory is absent. For the current mixing-directory layout, create real parent directories and follow `install-skills`' per-name procedure. Do not restore whole-directory links through the legacy CLI.
