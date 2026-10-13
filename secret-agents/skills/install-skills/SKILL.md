---
name: install-skills
description: "Install agent skills into harness discovery locations by creating junctions (Windows) or symlinks (Mac/Linux). Use when adding skills to a new machine, a new harness location, or refreshing after skills have been added or removed."
argument-hint: "[--all | <canonical-or-alias> ...] [--update] [--harness claude|codex|copilot|all | --target <directory>] [--help]"
user-invocable: true
---

# Install Skills

**Category:** Skill Management · **Short:** sis · **Updated:** 2026-10-10

Install agent skills into harness discovery locations. Creates a junction (Windows) or symlink (Mac/Linux) from each harness skill slot to the canonical skill directory — never copies files. Use `--update` to refresh the catalog before installing.

## Invocation / Flags

| Argument | Effect |
|---|---|
| *(none)* | Install all skills for the default harness (claude). |
| `--all` | Explicitly install all skills (same as no argument). |
| `<canonical-or-alias> ...` | Install only the named skills. Aliases resolve to their canonical target. |
| `--harness <harness>` | Target harness: `claude`, `codex`, `copilot`, or `all`. Default: `claude`. |
| `--target <directory>` | Install into a specific directory instead of the harness default. |
| `--update` | Run catalog update first, then install new or missing links. Safe to run repeatedly. |
| `--help` | Print the usage below and stop. Do not install anything. |

### `--help` output

When invoked with `--help`, respond with exactly this usage block and do nothing else:

```
install-skills — install agent skills as links into harness discovery locations

Usage:
  /install-skills                         Install all skills for the claude harness
  /install-skills --all                   Same as above
  /install-skills run-unit-tests          Install only the named skill(s)
  /install-skills --harness codex         Install for the codex harness
  /install-skills --harness all           Install for all known harnesses
  /install-skills --target <dir>          Install into a specific directory
  /install-skills --update                Refresh catalog then install new/missing skills
  /install-skills --help                  Show this help

Behavior:
  - Reads catalog.json to enumerate canonical skills and their aliases
  - Creates a junction (Windows) or symlink (Mac/Linux) in the target directory
  - Create-only: never removes or overwrites existing links
  - A conflict (existing path that is not a correct link) aborts before any mutation
  - --update runs catalog update first so new skills are picked up
  - Reports created and already-correct links; does NOT commit anything
```

## Procedure

Work from the skills root (`<skill base dir>\..`).

```bash
SKILL_DIR="<directory containing this SKILL.md>"
SKILLS_ROOT="$(dirname "$SKILL_DIR")"
```

### Step 1 — Optionally refresh the catalog

If `--update` is present:

```bash
python3 "$SKILL_DIR/../query-all-skills/scripts/catalog.py" update --skills-root "$SKILLS_ROOT"
```

If this exits non-zero, print the error and abort. Do not proceed to installation.

### Step 2 — Resolve the install set

Read `$SKILLS_ROOT/catalog.json`. Build the install set:

- No args or `--all`: every canonical entry plus its generated aliases.
- Named args: resolve each name (canonical name or alias) to its canonical skill directory. Report any name not found in the catalog and continue with the rest.

Determine the target directory from `--harness` / `--target`:

| Harness | Default target (Windows) | Default target (Mac/Linux) |
|---------|--------------------------|----------------------------|
| claude | `%USERPROFILE%\.claude\skills` | `~/.claude/skills` |
| codex | `%USERPROFILE%\.codex\skills` | `~/.codex/skills` |
| copilot | `%USERPROFILE%\.copilot\skills` | `~/.copilot/skills` |

`--target <dir>` overrides the harness default.

### Step 3 — Validate destinations before any mutation

For each skill in the install set, classify the destination path in the target directory:

- **correct**: a link already exists and points to the right canonical directory → skip.
- **will-create**: destination does not exist → will create a link.
- **conflict**: destination exists but is not a link, or is a link to a different target → abort.

If any destination is a conflict, print all conflicts and abort. Do not create any links.

### Step 4 — Create missing links

For each `will-create` destination, create a directory link using `secret-agents/src/secret_agents_setup/links.py`:

- Windows: directory junction (`WindowsLinkBackend.create_directory_link`).
- Mac/Linux: directory symlink (`PosixLinkBackend.create_directory_link`).

Each alias in the catalog points to the same canonical skill directory as its canonical entry.

### Step 5 — Report

Print one line per skill:
- `created:  <link-path> → <canonical-dir>`
- `ok:       <link-path> (already correct)`

End with a summary: `installed N new links; M already correct`.

## Notes

- Links are create-only: existing correct links are left untouched; the skill never removes or overwrites links.
- `--update` is idempotent: it refreshes the catalog and adds any skills that have been added since the last install run.
- To install for all harnesses: `/install-skills --harness all`.
- To install a single skill: `/install-skills run-unit-tests` (creates links for both the canonical name and its `rut` alias).
