---
name: reset-unreal-build-environment
description: Use when Unreal Engine builds, UGS builds, UBT/UAT/Build.bat/RunUAT.bat/GenerateProjectFiles, UBA, MSBuild, or Visual Studio shell state must be stopped or cleaned before starting a fresh Unreal build on Windows.
---

# Reset Unreal Build Environment

## Overview

Reset a Windows Unreal build shell before a fresh build. Prefer the bundled PowerShell helper because process trees, UBA workers, reusable MSBuild nodes, and Visual Studio environment variables are easy to miss by hand.

Core rule: stop build/tool processes, preserve editor and Perforce state unless the user explicitly asks otherwise.

## Quick Start

Run from the same PowerShell session that will start the next build:

```powershell
$Skill = "D:\git\worky\Agent\skills\reset-unreal-build-environment"
& "$Skill\scripts\Stop-UnrealBuildAndCleanEnv.ps1" -Root "D:\p4\ss-5.8\root"
```

Preview first when other Unreal work may be running:

```powershell
& "$Skill\scripts\Stop-UnrealBuildAndCleanEnv.ps1" -Root "D:\p4\ss-5.8\root" -WhatIf
```

If the root is unknown, omit `-Root`; the script auto-detects an Unreal root from the current directory, then falls back to clearly Unreal build-tool process matches.

## Behavior

The helper:

- Stops process trees seeded by `Build.bat`, `RunUAT.bat`, `GenerateProjectFiles.bat`, `UnrealBuildTool`, `AutomationTool`, UBA tools, Unreal-bundled `dotnet` MSBuild nodes, and compiler/linker children tied to the root.
- Clears current-process Visual Studio, MSBuild, .NET, UAT, and `uebp_*` environment variables that commonly poison Unreal builds.
- Sets `MSBUILDDISABLENODEREUSE=1`.
- Leaves `P4CLIENT`, `P4PORT`, `P4USER`, and other Perforce variables alone.
- Leaves `UnrealEditor.exe` alone unless `-IncludeEditor` is passed.

## Options

| Option | Use |
|---|---|
| `-Root <path>` | Scope process matching to one Unreal root. Prefer this whenever possible. |
| `-AllWorkspaces` | Stop clearly Unreal build processes across all roots. Use only when the user asks for all build activity. |
| `-IncludeEditor` | Also stop Unreal editor/game processes rooted in the workspace. Do not use for ordinary build cleanup. |
| `-SkipProcessStop` | Clean environment only. Useful for tests or when another build must continue. |
| `-SkipEnvironmentCleanup` | Stop processes only. |
| `-WhatIf` | Show what would be stopped/cleared without changing anything. |

## Common Mistakes

- Running the script through a new `powershell.exe` only cleans that child process's environment. Run it in the build shell before invoking `Build.bat`.
- Omitting `-Root` when multiple Unreal branches are building can stop more than intended.
- Clearing Perforce variables creates a different problem; this skill deliberately preserves them.
- Killing the editor by default can lose unsaved work; require `-IncludeEditor` for that.
