# UGS PCB Runbook and Skill Design

## Goal
Create a reliable, human-and-agent-friendly UGS PCB release workflow based on the final successful VisTest command set. The workflow should stay usable for VisTest by default while allowing future projects to override workspace, editor target, uproject, P4 client, and archive stream.

## Source Of Truth
Two artifacts must stay synchronized:

- `D:\p4\vistest\UGS_PCB_Runbook.md` for human copy/paste execution.
- `D:\git\worky\Agent\skills\ugs-pcb-release\SKILL.md` for agent execution.

Any future change to commands, defaults, validation checks, troubleshooting guidance, or Perforce behavior must update both artifacts in the same change. Each artifact should explicitly say to check the other before changing the process.

## Runbook Design
Move the current project-local `UGS_UBA_Runbook.md` into the shared worky runbook tree as `D:\\git\\worky\\Agent\\runbooks\\ugs-pcb\\UGS_PCB_Runbook.md` and rewrite it as a linear release checklist:

1. Set VisTest defaults and verify workspace/P4 context.
2. Clean shell, DotNet, MSBuild, and stale build processes.
3. Optionally refresh UBT/UAT/project files only when needed.
4. Build or clean-build `VisTestEditor` without `-game`.
5. Rebuild `ShaderCompileWorker` and verify `XGEControlWorker` hash parity.
6. Verify USD runtime DLL parity when `USDImporter` is enabled.
7. Run BuildGraph with `-p4 -NoSubmit` and no-UBA compile args.
8. Validate the local PCB zip for one BuildId, worker hashes, expected metadata, and headless editor smoke.
9. Run BuildGraph submit only after the no-submit artifact passes.
10. Verify submitted Perforce archive and perform consumer-side UGS launch validation.

Remove red-herring material that implies this builds the UGS desktop application, requires `-game`, requires `bBuildAllModules`, or treats the Kuper crash as PCB evidence. Keep troubleshooting only when it helps decide whether to clean rebuild, rebuild workers, refresh USD DLLs, or inspect logs.

## Skill Design
Create `ugs-pcb-release` in `D:\git\worky\Agent\skills`. The skill should trigger when a user asks Codex to build, validate, submit, troubleshoot, or update a UGS precompiled binary / PCB workflow for UnrealGameSync.

The skill should:

- Start by reading `D:\\git\\worky\\Agent\\runbooks\\ugs-pcb\\UGS_PCB_Runbook.md` when present.
- Use VisTest defaults unless the user supplies overrides.
- Require P4 workspace validation before any `-p4` command.
- Prefer no-submit BuildGraph before submit.
- Treat validation as mandatory evidence before success claims.
- Keep runbook and skill synchronized whenever either changes.
- Include compact default variables and successful command shapes, not long narrative history.

No wrapper script is required in this first pass. The skill can reference the runbook for full copy/paste blocks and carry only the agent decision workflow plus essential defaults.

## Discoverability Design
Keep worky as the canonical shared source:

- `D:\git\worky\Agent\AGENTS.md`
- `D:\git\worky\Agent\skills\<skill-name>\SKILL.md`

Ensure the worky `AGENTS.md` explains how Codex should discover shared skills and fallback to `D:\git\worky\Agent\skills` when a skill is explicitly requested but not active.

Create or repair local symlinks so global agent guidance points to worky instead of becoming a divergent copy:

- `C:\Users\mmccusker\AGENTS.md` -> `D:\git\worky\Agent\AGENTS.md`
- `C:\Users\mmccusker\.codex\AGENTS.md` -> `D:\git\worky\Agent\AGENTS.md`

For skills, prefer per-skill junctions under `C:\Users\mmccusker\.agents\skills` when the directory already contains other entries.

## Validation
After implementation:

- Confirm `D:\\git\\worky\\Agent\\runbooks\\ugs-pcb\\UGS_PCB_Runbook.md` exists and the old project-local `D:\\p4\\vistest\\UGS_UBA_Runbook.md` no longer remains as the canonical runbook.
- Confirm the runbook contains the final no-submit and submit command sets.
- Confirm the skill has valid YAML frontmatter and required `SKILL.md` structure.
- Confirm worky `AGENTS.md` includes Codex discoverability/fallback instructions.
- Confirm home/Codex AGENTS symlinks point to worky.
- Do not rerun the full PCB build unless explicitly requested; this change is documentation/skill plumbing.

## Non-Goals
- Do not submit another PCB.
- Do not create a BuildGraph wrapper script yet.
- Do not fix the Kuper Qt crash here.
- Do not add `-game` or `bBuildAllModules` as default guidance.
