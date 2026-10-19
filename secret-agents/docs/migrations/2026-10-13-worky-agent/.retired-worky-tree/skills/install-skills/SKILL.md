---
name: install-skills
description: "Install agent skills from the shared skills folder so VS Code Copilot can discover them. Defaults: source is the shared skills folder (parent of this skill), target is the folder this skill is running from (its install location). Use --source and --target to override, --update to refresh an existing install after adding new skills, and --help for usage. Use when the user asks to install skills, enable skills, or update/refresh the skills installation."
argument-hint: "[--all | <skill-name> ...] [--source <dir>] [--target <dir>] [--update] [--help]"
user-invocable: true
---

# Install Skills

Copy agent skills from the shared skills folder into a Copilot discovery location so
they show up as slash commands.

By default the **source** is the shared skills folder (the parent of this skill's
directory) and the **target** is the folder this skill is running from (its install
location). Pass `--source` and `--target` to point them elsewhere, e.g.
`--target ~/.copilot/skills` for a machine-wide install (available in every workspace)
or `--target <repo>/.github/skills` for one repo.

## Paths

| Item | Path |
|---|---|
| Source skills folder (`--source`) | Parent of this skill's directory by default; override with `--source <dir>` |
| Target (`--target`) | The folder this skill is running from by default; override with `--target <dir>` (e.g. `~/.copilot/skills` for machine-wide, or `<repo>/.github/skills` for one repo) |

A "skill" is any subfolder of the source folder that contains a `SKILL.md`.

## Invocation / Flags

| Argument | Effect |
|---|---|
| *(none)* | Install **all** skills from the default source into the default target (the folder this skill is running from). |
| `--all` | Explicitly install all skills (same as no argument). |
| `<skill-name> ...` | Install only the named skill(s), e.g. `run-unit-tests rut`. |
| `--source <dir>` | Skills folder to copy from. Default: the shared skills folder (parent of this skill). |
| `--target <dir>` | Where to install. Default: the folder this skill is running from (its install location). |
| `--update` | Refresh an existing install: re-copy the selected skills (overwriting), so newly added or edited skills in the source folder are picked up. Safe to run repeatedly. |
| `--help` | Print the usage below and stop. Do not install anything. |

`--update` can be combined with a skill name or `--target`, e.g.
`/install-skills --update run-unit-tests` refreshes just that skill.

### `--help` output

When invoked with `--help`, respond with exactly this usage block and do nothing else:

```
install-skills — copy agent skills from the shared folder into a discovery location

Usage:
  /install-skills                             Install all skills (source: shared folder, target: this skill's folder)
  /install-skills --all                       Same as above
  /install-skills run-unit-tests rut          Install only the named skills
  /install-skills --source <dir>              Copy from a different skills folder
  /install-skills --target <dir>              Install into a different location (default: this skill's folder)
  /install-skills --target ~/.copilot/skills  Install machine-wide
  /install-skills --update                    Refresh an existing install (pick up new/edited skills)
  /install-skills --update run-unit-tests     Refresh just the named skill(s)
  /install-skills --help                      Show this help

Behavior:
  - Source: parent of this skill's directory (the shared skills folder); --source overrides
  - Target: the folder this skill is running from; --target overrides (e.g. ~/.copilot/skills)
  - Copies each skill folder (must contain SKILL.md), overwriting existing copies
  - Validates each SKILL.md frontmatter (valid YAML, name matches folder)
  - --update re-copies selected skills so new/edited ones are picked up
  - Reports which skills were installed and where
  - Does NOT commit anything
```

## Procedure

### Step 1 — Resolve source and target

- **Source (`--source`):** the shared skills folder, resolved as the parent of this
  skill's own directory. Override with `--source <dir>`.
- **Target (`--target`):** the folder this skill is running from by default (the parent
  of this SKILL.md's directory, i.e. its install location). Override with `--target <dir>`
  (relative paths resolve from the CWD).

```bash
SKILL_DIR="<directory containing this SKILL.md>"
SRC="${SOURCE:-$(dirname "$SKILL_DIR")}"     # --source; default: shared skills folder
TARGET="${TARGET:-$(dirname "$SKILL_DIR")}"  # --target; default: this skill's own folder
mkdir -p "$TARGET"
```

### Step 2 — Determine which skills to install

- No args or `--all`: every subfolder of `$SRC` that contains a `SKILL.md`.
- Named skills: only the named subfolders. If a named skill does not exist in `$SRC`,
  report it as missing and continue with the rest.

```bash
# List candidate skills (folders with a SKILL.md)
for d in "$SRC"/*/; do [ -f "$d/SKILL.md" ] && echo "$(basename "$d")"; done
```

### Step 3 — Copy each skill into the target

For each selected skill, copy its **folder** into the target, overwriting any existing
copy.

**Important — do not use a trailing slash on the source.** `cp -R "$SRC/<name>/"`
copies the folder's *contents* into the target and flattens every skill into one
top-level `SKILL.md`. Copy the folder itself by stripping the trailing slash:

```bash
cp -R "${d%/}" "$TARGET/"
```

Skip non-skill entries (e.g. `README.md`, `README.html`, `Untitled/`) — only folders
with a `SKILL.md` are skills.

### Step 4 — Validate the installed frontmatter

For each installed skill, confirm the `SKILL.md` frontmatter is valid YAML and the
`name` field matches the folder name:

```bash
python3 - "$TARGET" <<'PY'
import sys, yaml
from pathlib import Path
target = Path(sys.argv[1])
ok = True
n = 0
for skill_md in sorted(target.glob("*/SKILL.md")):
    n += 1
    text = skill_md.read_text(encoding="utf-8")
    try:
        fm = yaml.safe_load(text.split("---")[1])
    except Exception as e:
        print(f"INVALID YAML: {skill_md.parent.name}: {e}"); ok = False; continue
    name = fm.get("name")
    if name != skill_md.parent.name:
        print(f"NAME MISMATCH: folder '{skill_md.parent.name}' has name '{name}'"); ok = False
print(f"{n} skills checked ->", "ALL VALID" if ok else "PROBLEMS FOUND")
PY
```

**Checkpoint:** prints `N skills checked -> ALL VALID` (or lists the specific problems).
If a `description` fails to parse, it almost always has an unquoted colon — quote the
value in the source `SKILL.md` and re-copy that skill.

### Step 5 — Report

List each installed skill (name → target path) and the total count. Remind the user:

- **Machine-wide** (`~/.copilot/skills`): available in every workspace on this machine.
- **Per-repo** (`--target .github/skills`): available only in that workspace.
- Type `/` in chat to see the new slash commands.
- Nothing was committed.

## `--update` behavior

`--update` is for refreshing an existing installation after you add or edit skills in
the source folder. It performs the same copy + validate steps (Steps 1–5) but:

- Re-copies only the selected skills (all, or the named ones), overwriting what is
  already installed.
- Never removes skills that are no longer in the source folder — it only adds/updates.
  If the user wants to prune removed skills, say so explicitly and confirm before
  deleting anything.
- Is safe to run repeatedly (idempotent).

## Notes

- Copying (not symlinking) keeps each install self-contained and portable.
- Re-running is idempotent: existing copies are overwritten with the current source.
- Source defaults to the shared skills folder (parent of this skill); target defaults
  to the folder this skill is running from (its install location). Use `--source` /
  `--target` to point elsewhere. If source and target resolve to the same folder the run
  is an in-place refresh; pass `--source <shared folder>` to update an installed set from
  a different shared folder.
