---
name: query-all-skills
description: "List all installed agent skills from the shared skills folder, showing each skill name and pairing any shorthand alias with its parent on the same line, then tell the user how to get usage for a skill. Use when the user asks to list skills, see all skills, what skills exist, or says 'qas'."
argument-hint: "[--target <dir>] [--help]"
user-invocable: true
---

# Query All Skills

List every skill in the shared skills folder. Each skill is printed on its own
line; a skill that has a shorthand alias is shown with the shorthand in
parentheses on the same line (e.g. `run-unit-tests (rut)`). After the list, print
a short message telling the user how to get usage for any skill.

## Procedure

### Step 1 — List the skills

Run the bundled script (it scans the source folder and pairs shorthands). The script
lives next to this skill file, so resolve it relative to the skill's own directory
rather than a hardcoded path:

```bash
SKILL_DIR="<directory containing this SKILL.md>"
python3 "$SKILL_DIR/scripts/list_skills.py"
```

The script prints a header (`Skills (N) in <source>`) followed by one line per
skill. Shorthand skills are not printed as their own line — they appear inline
with their parent in parentheses.

With `--target <dir>`, list that folder instead of the default:

```bash
python3 "$SKILL_DIR/scripts/list_skills.py" "<--target value>"
```

### Step 2 — Print the usage message

Immediately after the list, print this message verbatim:

```
To see how to use any skill, run it with --help (most skills support this):
  /<skill-name> --help
Shorthand skills work the same way, e.g. /rut --help is the same as /run-unit-tests --help.
```

## Output example

```
Skills (17) in <source folder>

- architecture-guards
- install-skills
- jira-human-ticket-create (jira-ht)
- python-quality-gate
- python-tdd-cycle
- ready-player-one
- report-rollup
- reset-unreal-build-environment
- run-mac-coverage
- run-unit-tests (rut)
- status-report-create
- ugs-pcb-release
- update-claude-pricing-doc
- update-skills-readme
- work-receipt-create

To see how to use any skill, run it with --help (most skills support this):
  /<skill-name> --help
Shorthand skills work the same way, e.g. /rut --help is the same as /run-unit-tests --help.
```

## `--help`

When invoked with `--help`, print this and do nothing else:

```
query-all-skills — list all agent skills

Usage:
  /query-all-skills          List all skills (shorthands shown inline)
  /qas                       Short form of /query-all-skills

Each skill is listed on its own line. Skills with a shorthand alias show the
shorthand in parentheses on the same line, e.g. "run-unit-tests (rut)".
After the list, a message explains how to get usage for a skill (--help).
```

## Notes

- The default source folder is the current working directory; pass `--target <dir>`
  to list a different skills folder.
- Shorthand detection looks for a phrase that *declares* a skill to be an alias
  ("alias for …", "short form of …", "short version") and pairs it with the
  skill named right after that phrase. Requiring the "for"/"of" construction
  avoids matching skills that merely talk about aliases. If a new shorthand
  uses different wording, add the phrase to `ALIAS_MARKERS` in
  [list_skills.py](./scripts/list_skills.py).
