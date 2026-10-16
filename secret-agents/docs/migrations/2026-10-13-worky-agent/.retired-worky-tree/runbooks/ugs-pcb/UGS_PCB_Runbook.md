# UGS PCB Runbook

Build and submit UnrealGameSync precompiled editor binaries for VisTest.

This runbook is intentionally short. The normal flow is:

1. Set environment variables.
2. Build the editor.
3. Build `ShaderCompileWorker`.
4. Run BuildGraph no-submit.
5. Submit with BuildGraph.

Do **not** run this from `//vistest-vp/main-content`. BuildGraph must run from a `//vistest-vp/main` workspace so the archive name matches what UGS consumers sync:

```text
//ue-laika/editor-binaries/++vistest-vp+main-VisTestEditor.zip
```

## 1. Setup

Open plain PowerShell anywhere inside the correct workspace, then paste this block.

```powershell
$env:P4CLIENT = "vt-main_mmccusker_dp58-130"

$Here = (Resolve-Path ".").Path

while ($Here -and -not (Test-Path (Join-Path $Here "Engine\Build\BatchFiles\RunUAT.bat"))) {
  if (Test-Path (Join-Path $Here "root\Engine\Build\BatchFiles\RunUAT.bat")) {
    $Here = Join-Path $Here "root"
    break
  }
  $Parent = Split-Path $Here -Parent
  if ($Parent -eq $Here) { throw "Could not find Unreal root. Run from inside the workspace." }
  $Here = $Parent
}

$Root = $Here
Set-Location $Root

p4 login -s
if ($LASTEXITCODE -ne 0) {
  p4 login
}

$Project = Join-Path $Root "Content\VisTest\VisTest.uproject"
$ProjectDir = Split-Path $Project -Parent
$ProjectName = "VisTest"
$EditorTarget = "VisTestEditor"
$UgsConfig = Join-Path $ProjectDir "Build\UnrealGameSync.ini"
$ExpectedArchivePath = (
  Select-String -Path $UgsConfig -Pattern "^ZippedBinariesPath=(\S+)" |
  Select-Object -First 1
).Matches.Groups[1].Value
$ArchiveStream = $ExpectedArchivePath.Substring(0, $ExpectedArchivePath.LastIndexOf("/"))
$ExpectedZipName = Split-Path $ExpectedArchivePath -Leaf
$ExpectedMajorVersion = 5
$ExpectedMinorVersion = 7
$ExpectedPatchVersion = 4
$ExpectedBranchName = "++vistest-vp+main"

$Info = p4 -ztag info
$ClientStream = (($Info | Where-Object { $_ -like "... clientStream *" } | Select-Object -First 1) -replace "^\.\.\. clientStream ", "").Trim()

if ($ClientStream -ne "//vistest-vp/main") {
  throw "Wrong Perforce stream: '$ClientStream'. Open a //vistest-vp/main workspace before building the PCB."
}

[pscustomobject]@{
  Root = $Root
  Project = $Project
  ClientStream = $ClientStream
  ArchivePath = $ExpectedArchivePath
  ExpectedZipName = $ExpectedZipName
  ExpectedVersion = "$ExpectedMajorVersion.$ExpectedMinorVersion.$ExpectedPatchVersion"
  ExpectedBranchName = $ExpectedBranchName
} | Format-List
```

Expected:

- `ClientStream` is `//vistest-vp/main`
- `ArchivePath` is `//ue-laika/editor-binaries/++vistest-vp+main-VisTestEditor.zip`
- `ExpectedVersion` is `5.7.4`
- `ExpectedBranchName` is `++vistest-vp+main`

Stop if either value is different.

## 2. Clean The Shell

```powershell
"VisualStudioDir","VSSKUEDITION","PkgDefApplicationConfigFile","VSAPPIDDIR",
"VisualStudioEdition","VisualStudioVersion","DOTNET_ROOT","DOTNET_ROOT(x86)",
"MSBuildSDKsPath","MSBuildExtensionsPath","MSBUILD_EXE_PATH" |
  ForEach-Object { Remove-Item "Env:\$_" -ErrorAction SilentlyContinue }

$env:MSBUILDDISABLENODEREUSE = "1"

Get-Process dotnet,msbuild,vbcscompiler,UnrealBuildTool,UbaServer,UbaSessionServer,UbaAgent -ErrorAction SilentlyContinue |
  Stop-Process -Force
```

## 3. Build The Editor

```powershell
& ".\Engine\Build\BatchFiles\Build.bat" $EditorTarget Win64 Development "-Project=$Project" -WaitMutex -NoUBA -NoUBALocalExecutor -Clean
& ".\Engine\Build\BatchFiles\Build.bat" $EditorTarget Win64 Development "-Project=$Project" -Progress -Unattended -WaitMutex -NoUBA -NoUBALocalExecutor
```

## 4. Build ShaderCompileWorker

This must be rebuilt for the PCB. UGS consumers should not compile binaries locally.

```powershell
& ".\Engine\Build\BatchFiles\Build.bat" ShaderCompileWorker Win64 Development -WaitMutex -NoUBA -NoUBALocalExecutor -Clean
& ".\Engine\Build\BatchFiles\Build.bat" ShaderCompileWorker Win64 Development -WaitMutex -NoUBA -NoUBALocalExecutor

Get-FileHash ".\Engine\Binaries\Win64\ShaderCompileWorker.exe", ".\Engine\Binaries\Win64\XGEControlWorker.exe" -Algorithm SHA256
```

Expected: both files exist. Keep the hash output for the release note.

## 5. BuildGraph No-Submit

This creates the zip locally without submitting it.

```powershell
& ".\Engine\Build\BatchFiles\RunUAT.bat" BuildGraph `
  -Script="Engine/Build/Graph/Examples/BuildEditorAndTools.xml" `
  -Target="Submit To Perforce For UGS" `
  "-set:EditorTarget=$EditorTarget" `
  "-set:UProjectPath=$Project" `
  "-set:ArchiveStream=$ArchiveStream" `
  '-set:EditorCompileArgs=-NoUBA -NoUBALocalExecutor' `
  '-set:ToolCompileArgs=-NoUBA -NoUBALocalExecutor' `
  -p4 -NoSubmit `
  -unattended -noturnkeyvariables `
  -UTF8Output
```

Validate the zip name:

```powershell
$Zip = Get-ChildItem ".\LocalBuilds\ArchiveForUGS-Perforce" -File -Filter "*.zip" |
  Sort-Object LastWriteTime -Descending |
  Select-Object -First 1

$Zip.FullName
$Zip.Name -eq $ExpectedZipName
```

Expected: the last line is `True`.

If the zip name contains `main-content`, stop. You are in the wrong workspace.

Validate the zip version:

```powershell
Add-Type -AssemblyName System.IO.Compression.FileSystem

$Archive = [System.IO.Compression.ZipFile]::OpenRead($Zip.FullName)
try {
  $VersionEntry = $Archive.Entries | Where-Object FullName -eq "Engine/Binaries/Win64/UnrealEditor.version" | Select-Object -First 1
  if (-not $VersionEntry) { throw "Zip is missing Engine/Binaries/Win64/UnrealEditor.version" }

  $Reader = [IO.StreamReader]::new($VersionEntry.Open())
  try {
    $EditorVersion = $Reader.ReadToEnd() | ConvertFrom-Json
  }
  finally {
    $Reader.Dispose()
  }
}
finally {
  $Archive.Dispose()
}

$VersionMatches =
  $EditorVersion.MajorVersion -eq $ExpectedMajorVersion -and
  $EditorVersion.MinorVersion -eq $ExpectedMinorVersion -and
  $EditorVersion.PatchVersion -eq $ExpectedPatchVersion -and
  $EditorVersion.BranchName -eq $ExpectedBranchName -and
  -not [string]::IsNullOrWhiteSpace($EditorVersion.BuildId)

[pscustomobject]@{
  Zip = $Zip.Name
  Version = "$($EditorVersion.MajorVersion).$($EditorVersion.MinorVersion).$($EditorVersion.PatchVersion)"
  BranchName = $EditorVersion.BranchName
  BuildId = $EditorVersion.BuildId
  VersionMatches = $VersionMatches
} | Format-List

if (-not $VersionMatches) {
  throw "Zip has the wrong UnrealEditor.version. Expected $ExpectedMajorVersion.$ExpectedMinorVersion.$ExpectedPatchVersion $ExpectedBranchName with a populated BuildId."
}
```

Expected:

- `Version` is `5.7.4`
- `BranchName` is `++vistest-vp+main`
- `BuildId` is populated
- `VersionMatches` is `True`

Stop if the zip reports `5.3.2`, `++vistest-vp+main-content`, or any other unexpected version/branch.

## 6. Launch The Built Editor

Launch the editor you just built and confirm VisTest opens successfully before you submit the PCB.

```powershell
& ".\Engine\Binaries\Win64\UnrealEditor.exe" "$Project"
```

Expected: the editor launches successfully with the VisTest project. Close it after the manual check completes.

## 7. Submit

Only run this after the no-submit zip name and zip version are correct.

```powershell
& ".\Engine\Build\BatchFiles\RunUAT.bat" BuildGraph `
  -Script="Engine/Build/Graph/Examples/BuildEditorAndTools.xml" `
  -Target="Submit To Perforce For UGS" `
  "-set:EditorTarget=$EditorTarget" `
  "-set:UProjectPath=$Project" `
  "-set:ArchiveStream=$ArchiveStream" `
  '-set:EditorCompileArgs=-NoUBA -NoUBALocalExecutor' `
  '-set:ToolCompileArgs=-NoUBA -NoUBALocalExecutor' `
  -p4 -submit `
  -unattended -noturnkeyvariables `
  -UTF8Output
```

## 8. Verify Submit

```powershell
p4 files "$ExpectedArchivePath"
p4 fstat -Ol "$ExpectedArchivePath"
```

Expected: the submitted depot file is:

```text
//ue-laika/editor-binaries/++vistest-vp+main-VisTestEditor.zip
```

## If Something Fails

- Wrong stream: switch to a `//vistest-vp/main` workspace. Do not build from `//vistest-vp/main-content`.
- Zip name contains `main-content`: wrong workspace; rerun from `//vistest-vp/main`.
- Missing modules in UGS: verify UGS is syncing `++vistest-vp+main-VisTestEditor.zip`, not an old or wrong archive.
- Shader worker mismatch: rebuild `ShaderCompileWorker`, rerun no-submit, then submit again.
- Build.version: do not add it to VisTest. It should come from `//ue-laika/ue-local-5.7.4/Engine/Build/Build.version`.
