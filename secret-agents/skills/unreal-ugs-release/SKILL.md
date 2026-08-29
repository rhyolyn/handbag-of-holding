---
name: unreal-ugs-release
description: Use when building, validating, submitting, troubleshooting, or updating UnrealGameSync UGS precompiled editor binaries, PCB archives, BuildGraph Submit To Perforce For UGS flows, no-submit validation, shader worker mismatches, or UGS archive runbooks.
---

# UGS PCB Release

## Canonical Runbook

Read this first:

```text
D:\git\worky\Agent\runbooks\ugs-pcb\UGS_PCB_Runbook.md
```

The runbook is the human copy/paste source. This skill is the agent operating guide. Keep them synchronized.

## Sync Rule

Any change to commands, defaults, validation, troubleshooting, or Perforce behavior must update both:

- `D:\git\worky\Agent\runbooks\ugs-pcb\UGS_PCB_Runbook.md`
- `D:\git\worky\Agent\skills\unreal-ugs-release\SKILL.md`

Do not leave one artifact stale.

## Default Profile

Use these defaults unless the user supplies overrides:

| Setting | Default |
|---|---|
| Workspace | Current P4 client workspace root (derive from resolved repo root) |
| Root | Auto-detect from current directory: use current directory if it contains `Engine\`; otherwise use child `root\` if present |
| UProject | `<Root>\Content\VisTest\VisTest.uproject` |
| Editor target | `VisTestEditor` |
| Archive stream | `//ue-laika/editor-binaries` |
| UGS archive path | `//ue-laika/editor-binaries/++vistest-vp+main-VisTestEditor.zip` |
| Expected editor version | `5.7.4` |
| Expected archive branch | `++vistest-vp+main` |
| P4 stream for publishing | `//vistest-vp/main` |
| P4 client | The human runbook sets window-scoped `P4CLIENT=vt-main_mmccusker_dp58-130` before validation; otherwise auto-detect from current location by matching client root + expected stream |

For other projects, resolve these before running commands: workspace root, repo root containing `Engine\`, `.uproject`, editor target, archive stream, UGS-configured archive path, publishing stream, and Perforce client.

For VisTest, `Content\VisTest\Build\UnrealGameSync.ini` is the source of truth for what UGS consumers sync:

```text
ZippedBinariesPath=//ue-laika/editor-binaries/++vistest-vp+main-VisTestEditor.zip
```

Do not submit VisTest PCBs to `++vistest-vp+main-content-VisTestEditor.zip`. BuildGraph derives the zip name from the client stream's escaped branch, so running from `//vistest-vp/main-content` creates a valid-looking archive in the wrong depot file.

## Required Workflow

Operator guidance to mirror in responses:

- Keep the human runbook short: setup, clean shell, build editor, build `ShaderCompileWorker`, BuildGraph no-submit, BuildGraph submit.
- Include only essential guards in the fast path: Perforce login must be valid, current Perforce stream must be `//vistest-vp/main`, and local zip name must match `ZippedBinariesPath`.
- Do not hard-code the runbook path, make the runbook parse itself, or add a large general-purpose Perforce client resolver to the human fast path.
- Derive `ArchiveStream` and expected zip name from `Content\VisTest\Build\UnrealGameSync.ini`.
- Require a no-submit BuildGraph pass before submit.
- Keep deeper diagnostics in troubleshooting or separate handoff notes, not in the primary operator flow.

1. Read the canonical runbook.
2. Confirm or set the project profile.
3. Read the project `Build\UnrealGameSync.ini` and verify `ZippedBinariesPath` before building.
4. Set or resolve `P4CLIENT` before running `p4 -ztag info`; for VisTest, the runbook sets `vt-main_mmccusker_dp58-130`, and the publishing client stream must be `//vistest-vp/main`.
5. Re-validate client and stream before any `-p4` command.
6. Clean DotNet/MSBuild/Visual Studio environment variables and stop stale build processes.
7. Optionally refresh UBT/UAT/project files only when tool state is stale.
8. Build or clean-build the editor target; do not add `-game` for editor PCB.
9. Clean-build `ShaderCompileWorker`; verify `ShaderCompileWorker.exe` and `XGEControlWorker.exe` hashes match.
10. Verify USD runtime DLL parity when `USDImporter` is enabled.
11. Run BuildGraph with `-p4 -NoSubmit`.
12. Validate the local PCB zip name matches the UGS-configured archive path, then validate `Engine/Binaries/Win64/UnrealEditor.version`, one BuildId, required files, and worker hashes.
13. Launch Unreal successfully before submit. In the human runbook, this is an interactive manual launch of the freshly built editor with the target `.uproject`; in automated validation, an equivalent smoke launch is acceptable.
14. Only after validation passes, rerun BuildGraph with `-p4 -submit`.
15. Verify the submitted Perforce archive at the exact `ZippedBinariesPath` and perform clean UGS consumer launch validation.

## Successful BuildGraph Shape

Use the runbook for copy/paste commands. The successful command shape includes:

- `RunUAT.bat BuildGraph`
- `-Script="Engine/Build/Graph/Examples/BuildEditorAndTools.xml"`
- `-Target="Submit To Perforce For UGS"`
- `-set:EditorTarget=<EditorTarget>`
- `-set:UProjectPath=<uproject>`
- `-set:ArchiveStream=<archive-stream>`
- `-set:EditorCompileArgs=-NoUBA -NoUBALocalExecutor`
- `-set:ToolCompileArgs=-NoUBA -NoUBALocalExecutor`
- `-p4 -NoSubmit` for validation
- `-p4 -submit` only after validation
- `-unattended -noturnkeyvariables -UTF8Output`

Do not default to `-game`, `-set:GameTargets=...`, or `bBuildAllModules = true`.

For VisTest, run this from a `//vistest-vp/main` workspace so the generated `$(EscapedBranch)-$(ArchiveName).zip` is `++vistest-vp+main-VisTestEditor.zip`, matching `UnrealGameSync.ini`.

## Validation Evidence

Before claiming the PCB is ready or fixed, collect concrete evidence:

- `p4 info` shows the intended client/root.
- The project `Build\UnrealGameSync.ini` `ZippedBinariesPath` has been read and matches the intended submitted archive.
- BuildGraph exits with code `0`.
- Zip exists under `LocalBuilds\ArchiveForUGS-Perforce`.
- Zip filename matches the UGS-configured archive path.
- Zip `Engine/Binaries/Win64/UnrealEditor.version` reports `5.7.4`, branch `++vistest-vp+main`, and a populated BuildId.
- All `UnrealEditor.modules` entries in the zip share exactly one BuildId.
- `Engine\Build\PrecompiledBinaries.txt` exists in the zip.
- `ShaderCompileWorker.exe` and `XGEControlWorker.exe` exist in the zip and hash-match local rebuilt binaries.
- The freshly built Unreal editor launches successfully for the target project before submit.
- Headless editor smoke does not show missing modules, mixed BuildIds, failed plugin loads, missing imports, or fatal errors.
- Submit log shows `BUILD SUCCESSFUL` and a Perforce changelist.
- Perforce `fstat -Ol` digest for the UGS-configured archive path matches the local zip hash.
- A clean UGS consumer workspace syncs the archive and launches without local compilation.

## Troubleshooting Boundaries

- Missing modules or mixed BuildIds: clean-build editor, rebuild workers, rerun no-submit, revalidate.
- Missing modules only in a clean UGS consumer workspace: first verify `UnrealGameSync.ini` `ZippedBinariesPath` and the submitted archive path. A correct PCB submitted to the wrong archive filename is still invisible to UGS consumers.
- Stale or wrong editor version in a clean UGS consumer workspace, such as `5.3.2` or branch `++vistest-vp+main-content`: inspect the submitted zip's `Engine/Binaries/Win64/UnrealEditor.version` before rebuilding; this usually indicates the wrong archive was synced or submitted.
- Shader worker input-version mismatch: rebuild `ShaderCompileWorker`, verify `XGEControlWorker`, rerun BuildGraph.
- USD loader errors: refresh USD runtime DLLs from checked-in USD SDK binaries.
- Wrong P4 client: stop and fix `P4CLIENT`; do not continue with `-p4`.
- If `p4 info` shows `Client name: <your ...> (illegal)`, clear `P4CLIENT` and set a real client name.
- Post-launch tool crashes are separate investigations unless they happen during editor startup or module load.

## Completion

When updating the process, report both changed artifacts. When running a PCB release, report the exact log path, zip path, `UnrealEditor.version` result, BuildId count, worker hash result, smoke-test result, and submitted changelist if submit was performed.
