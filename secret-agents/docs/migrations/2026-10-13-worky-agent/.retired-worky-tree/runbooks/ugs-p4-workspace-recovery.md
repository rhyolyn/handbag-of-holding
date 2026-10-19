# UGS + P4 Multi-Workspace Recovery (Windows)

## Why this exists
If you switch versions/changelists while a build is in progress (or while stale generated artifacts exist), Unreal unity/intermediate files can reference paths that no longer exist. This commonly surfaces as `fatal error C1083` for a missing `.cpp` include inside a generated `Module.*.cpp` file.

## Safe command sequence (PowerShell)

> Replace values in angle brackets before running.

```powershell
# 0) Set these explicitly to avoid using the wrong workspace
$Client = "<P4_CLIENT_NAME>"
$Root = "<WorkspaceRoot>"   # Example: C:\Users\ians\Perforce\ians_dp58-137_scout58\root
$CL = "<TargetCL>"           # Example: 12345678
$Project = "$Root\Content\ScoutingApp\ScoutingApp.uproject"

# 1) Verify you are talking to the intended Perforce client
p4 -c $Client info
p4 -c $Client where "$Root\..."

# 2) Sync exactly to the target CL and clean local drift
# (Use @=$CL to force exact changelist state.)
p4 -c $Client sync "$Root\...@=$CL"
p4 -c $Client clean "$Root\..."

# 3) Kill stale generated outputs (do not delete tracked source)
$toDelete = @(
  "$Root\Content\ScoutingApp\Intermediate",
  "$Root\Content\ScoutingApp\Binaries",
  "$Root\Engine\Plugins\Developer\Concert\ConcertApp\MultiUserClient\Intermediate",
  "$Root\Engine\Plugins\Developer\Concert\ConcertApp\MultiUserClient\Binaries"
)

foreach ($p in $toDelete) {
  if (Test-Path $p) {
    Remove-Item -Recurse -Force $p
  }
}

# Optional: clear local DDC for stubborn cache issues
# Remove-Item -Recurse -Force "$Root\Engine\DerivedDataCache"

# 4) Regenerate project files
Set-Location $Root
.\GenerateProjectFiles.bat

# 5) Rebuild editor target from clean generated state
# Pick one command style and keep it consistent in your team.

# Style A: UBT directly
.\RunUBT.bat UnrealEditor Win64 DebugGame -Project="$Project" -TargetType=Editor -Progress

# Style B: Build.bat (if your team standardizes on this)
# .\Engine\Build\BatchFiles\Build.bat UnrealEditor Win64 DebugGame -Project="$Project" -TargetType=Editor -Progress
```

## Notes for UGS + multiple clients
- Always confirm `p4 -c <client> info` before sync/build.
- Avoid changing CL while a build is running.
- If switching branches/streams or large CL jumps, always run `p4 clean` and delete Intermediate/Binaries before the next build.
- In UGS, ensure the selected workspace/client matches the one you use in P4V/CLI.
- If this still fails at the same missing file after clean sync, check depot contents for that exact CL/stream (possible missing delete/add integration).
