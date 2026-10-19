# Harness Setup Runbook

How to wire a machine or a new harness to the shared agent guidance in `<agent-root>`. Extracted verbatim-in-substance from `AGENTS.md` (revision 2026-07-11b) on 2026-07-12; the always-on per-session rules (skill fallback, runbook lookup, symlink-not-copy) stay in `AGENTS.md` § Environment & Harness Adapters.

## Principles

- `<agent-root>` (the directory containing `AGENTS.md`) is the canonical source of truth for shared guidance, portable skills, and shared runbooks.
- Treat harness-specific files and directories as adapters that point back to `<agent-root>`. Never copy shared guidance, skills, or runbooks into harness-specific folders when a symlink or junction will work.
- Prefer open-standard filenames and layouts so the same content works across harnesses without rewrites: `AGENTS.md` over `agent.md`; `SKILL.md` skills following the open Agent Skills structure.
- Keep harness-specific notes small and isolated so shared content stays portable.
- When adding a new harness, add its adapter path and discovery rule below instead of forking content.

## Canonical Layout

- `AGENTS.md` — shared instruction file.
- `skills\` — one subdirectory per skill, each with a top-level `SKILL.md`; optional assets under `references\`, `scripts\`, or `assets\` inside the skill directory.
- `runbooks\` — one subdirectory per reusable workflow; project-agnostic unless explicitly labeled as project defaults.

## Known Locations

This repo lives across two systems:

- `C:\git\worky\Agent`
- `D:\git\worky\Agent`

Symlinks and junctions cannot be relative across drives — resolve `<agent-root>` to the local absolute path before creating adapters.

## Adapter Rules (any harness)

- Global `AGENTS.md` support: file symlink from the harness-global location back to `<agent-root>\AGENTS.md`.
- Agent Skills discovery: directory symlink or junction from the harness skill location to each shared skill directory — or to the shared `skills\` directory when the harness path is otherwise empty. If the harness path already contains other entries, link per skill instead of replacing the directory.
- Different instruction filename required: symlink to `AGENTS.md` rather than maintaining a second real file.
- Different skill discovery path required: point it at this repository instead of duplicating skills.

## Codex

- Global shared guidance: `%USERPROFILE%\.codex\AGENTS.md` -> `<agent-root>\AGENTS.md`
- Home bootstrap: `%USERPROFILE%\AGENTS.md` — lightweight setup instructions for all harnesses; on a configured machine this is a standalone file, not a symlink to the shared file. Prefer `%USERPROFILE%\.codex\AGENTS.md` for the canonical guidance link.
- Global user skills: `%USERPROFILE%\.agents\skills\` -> `<agent-root>\skills\` (junction) or `%USERPROFILE%\.agents\skills\<skill-name>` -> `<agent-root>\skills\<skill-name>` (per-skill symlinks).

## Claude

- Global shared guidance: `%USERPROFILE%\.claude\AGENTS.md` -> `<agent-root>\AGENTS.md`
- Claude Code also discovers project-level `AGENTS.md` and `CLAUDE.md`; prefer `AGENTS.md` for cross-harness portability.
- Global user skills: `%USERPROFILE%\.claude\skills\` -> `<agent-root>\skills\` (junction). If empty or absent, create the whole-directory junction rather than per-skill symlinks so new skills appear automatically. Worky skills use `SKILL.md` format, invoked via the harness Skill tool.

## Copilot

- Setup path TBD. Update this section once the Copilot user-level instruction file path is confirmed for each machine.

## Verifying an Adapter

Ask the agent: "what revision of the shared guidance is loaded?" A correct revision date proves the adapter works; a wrong or missing answer means the symlink/junction is broken on this harness or machine — recreate it per the rules above, then ask for a full re-read.
