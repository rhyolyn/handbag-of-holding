# UGS PCB Runbook Skill Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move the UGS PCB workflow into shared worky docs and create a reusable Codex skill for future PCB releases.

**Architecture:** Keep the human runbook and agent skill as paired artifacts in `D:\git\worky\Agent`. The runbook carries full copy/paste commands; the skill carries agent workflow, defaults, and synchronization rules.

**Tech Stack:** Markdown runbook, Agent Skills `SKILL.md`, Windows PowerShell, Unreal UBT/UAT/BuildGraph, Perforce.

**Correction added 2026-07-07:** For VisTest PCB publishing, `Content\VisTest\Build\UnrealGameSync.ini` is the source of truth for the archive UGS consumers sync. It points to `//ue-laika/editor-binaries/++vistest-vp+main-VisTestEditor.zip`, so BuildGraph must be run from a `//vistest-vp/main` publishing workspace. Running from `//vistest-vp/main-content` produces `++vistest-vp+main-content-VisTestEditor.zip`, which UGS consumers do not use.

---

## File Structure

- Create: `D:\git\worky\Agent\runbooks\ugs-pcb\UGS_PCB_Runbook.md` — canonical human runbook.
- Create: `D:\git\worky\Agent\skills\ugs-pcb-release\SKILL.md` — canonical agent skill.
- Modify: `D:\git\worky\Agent\AGENTS.md` — shared Codex discoverability instructions and home symlink note.
- Create: `C:\Users\mmccusker\AGENTS.md` symlink to `D:\git\worky\Agent\AGENTS.md`.
- Create: `C:\Users\mmccusker\.codex\AGENTS.md` symlink to `D:\git\worky\Agent\AGENTS.md`.
- Create: `C:\Users\mmccusker\.agents\skills\ugs-pcb-release` junction to `D:\git\worky\Agent\skills\ugs-pcb-release`.
- Remove or archive: `D:\p4\vistest\UGS_UBA_Runbook.md` after canonical copy exists.

---

### Task 1: Move And Rewrite Runbook

**Files:**
- Create: `D:\git\worky\Agent\runbooks\ugs-pcb\UGS_PCB_Runbook.md`
- Remove: `D:\p4\vistest\UGS_UBA_Runbook.md`

- [ ] Create the shared runbook directory.

Run: `New-Item -ItemType Directory -Force -Path 'D:\git\worky\Agent\runbooks\ugs-pcb'`
Expected: directory exists.

- [ ] Write `UGS_PCB_Runbook.md` with these sections: purpose, defaults, clean environment, optional build tools, editor build, worker build, USD parity, no-submit BuildGraph, validation, submit, post-submit verification, troubleshooting, sync rule.

- [ ] Include the current Bootstrap And Autodetect block from the canonical runbook instead of fixed workspace variables. The bootstrap must derive `$Root`, `$Project`, `$EditorTarget`, `$ExpectedArchivePath`, `$ArchiveStream`, `$ExpectedClientStream`, and `$ExpectedZipName` from the local workspace plus `Content\VisTest\Build\UnrealGameSync.ini`, then auto-select a Perforce client mapped to `//vistest-vp/main`.

- [ ] Include the successful no-submit command with `-p4 -NoSubmit`, `-set:UProjectPath`, `-set:ArchiveStream`, no-UBA compile args, `-unattended`, `-noturnkeyvariables`, and `-UTF8Output`.

- [ ] Include the successful submit command with `-p4 -submit` and the same arguments.

- [ ] Remove red-herring guidance: no UGS desktop app build path, no default `-game`, no default `bBuildAllModules`, no Kuper crash troubleshooting.

- [ ] Delete `D:\p4\vistest\UGS_UBA_Runbook.md` after the shared runbook is written.

---

### Task 2: Create Agent Skill

**Files:**
- Create: `D:\git\worky\Agent\skills\ugs-pcb-release\SKILL.md`

- [ ] Create the skill directory.

Run: `New-Item -ItemType Directory -Force -Path 'D:\git\worky\Agent\skills\ugs-pcb-release'`
Expected: directory exists.

- [ ] Write frontmatter exactly with `name: ugs-pcb-release` and a trigger description for UGS PCB, precompiled binaries, BuildGraph, UGS archive, no-submit validation, and submit workflows.

- [ ] Add required workflow: read the runbook first, resolve defaults/overrides, clean env, validate P4 client, build editor, rebuild workers, run no-submit BuildGraph, validate zip, smoke test, submit only after validation, post-submit verify.

- [ ] Add the runbook-skill synchronization rule: any command/default/validation/troubleshooting change must update both artifacts in the same change.

- [ ] Add compact default variable table for VisTest and note which values to override for other projects.

---

### Task 3: Update Discoverability And Links

**Files:**
- Modify: `D:\git\worky\Agent\AGENTS.md`
- Create symlink: `C:\Users\mmccusker\AGENTS.md`
- Create symlink: `C:\Users\mmccusker\.codex\AGENTS.md`
- Create junction: `C:\Users\mmccusker\.agents\skills\ugs-pcb-release`

- [ ] Ensure `AGENTS.md` says worky is canonical for shared runbooks as well as skills.

- [ ] Ensure `AGENTS.md` says Codex should check `D:\git\worky\Agent\skills\<skill-name>\SKILL.md` when a named skill is not active.

- [ ] Create home and Codex AGENTS symlinks to the worky AGENTS file.

Run:

```powershell
New-Item -ItemType SymbolicLink -Path 'C:\Users\mmccusker\AGENTS.md' -Target 'D:\git\worky\Agent\AGENTS.md'
New-Item -ItemType SymbolicLink -Path 'C:\Users\mmccusker\.codex\AGENTS.md' -Target 'D:\git\worky\Agent\AGENTS.md'
```

Expected: both paths have `LinkType` of `SymbolicLink` and target the worky file.

- [ ] Create the skill junction.

Run: `New-Item -ItemType Junction -Path 'C:\Users\mmccusker\.agents\skills\ugs-pcb-release' -Target 'D:\git\worky\Agent\skills\ugs-pcb-release'`
Expected: junction target is the worky skill directory.

---

### Task 4: Validate Documentation And Skill Plumbing

**Files:**
- Validate: `D:\git\worky\Agent\runbooks\ugs-pcb\UGS_PCB_Runbook.md`
- Validate: `D:\git\worky\Agent\skills\ugs-pcb-release\SKILL.md`
- Validate: `D:\git\worky\Agent\AGENTS.md`

- [ ] Confirm the old project-local runbook is gone.

Run: `Test-Path 'D:\p4\vistest\UGS_UBA_Runbook.md'`
Expected: `False`.

- [ ] Confirm the new runbook exists and includes both BuildGraph commands.

Run: `Select-String -LiteralPath 'D:\git\worky\Agent\runbooks\ugs-pcb\UGS_PCB_Runbook.md' -Pattern '-NoSubmit','-submit','ShaderCompileWorker','XGEControlWorker','UGS_PCB_Runbook.md','ugs-pcb-release'`
Expected: matches for all patterns.

- [ ] Confirm the skill has valid required frontmatter.

Run: `Get-Content 'D:\git\worky\Agent\skills\ugs-pcb-release\SKILL.md' -First 8`
Expected: YAML block includes `name` and `description`.

- [ ] Confirm symlinks and junctions.

Run: `Get-Item 'C:\Users\mmccusker\AGENTS.md','C:\Users\mmccusker\.codex\AGENTS.md','C:\Users\mmccusker\.agents\skills\ugs-pcb-release' | Select-Object FullName,LinkType,Target`
Expected: two symbolic links and one junction targeting worky.

- [ ] Do not run a full PCB build during this documentation/skill change.
