---
name: qas
description: "Short alias for the query-all-skills skill. Lists all installed agent skills, pairing any shorthand alias with its parent on the same line, then tells the user how to get usage for a skill. Use when the user types 'qas' or asks to quickly list all skills."
argument-hint: "[--target <dir>] [--help]"
user-invocable: true
---

# qas (query-all-skills, short form)

`/qas` is the short alias for the `query-all-skills` skill. It performs the exact
same workflow. If the `query-all-skills` skill is available, follow it; otherwise
follow the self-contained procedure below.

## Procedure

### Step 1 — List the skills

Run the bundled script from the `query-all-skills` skill (it scans the source folder
and pairs shorthands). Resolve it relative to this skill's own directory:

```bash
SKILL_DIR="<directory containing this SKILL.md>"
python3 "$SKILL_DIR/../query-all-skills/scripts/list_skills.py"
```

The script prints a header (`Skills (N) in <source>`) followed by one line per
skill. Shorthand skills are not printed as their own line — they appear inline
with their parent in parentheses.

With `--target <dir>`, list that folder instead of the default:

```bash
python3 "$SKILL_DIR/../query-all-skills/scripts/list_skills.py" "<--target value>"
```

### Step 2 — Print the usage message

Immediately after the list, print this message verbatim:

```
To see how to use any skill, run it with --help (most skills support this):
  /<skill-name> --help
Shorthand skills work the same way, e.g. /rut --help is the same as /run-unit-tests --help.
```

## `--help`

When invoked with `--help`, print this and do nothing else:

```
qas — short form of query-all-skills (list all agent skills)

Usage:
  /qas               List all skills (shorthands shown inline)
  /query-all-skills  Same as /qas

Each skill is listed on its own line. Skills with a shorthand alias show the
shorthand in parentheses on the same line, e.g. "run-unit-tests (rut)".
After the list, a message explains how to get usage for a skill (--help).
```
