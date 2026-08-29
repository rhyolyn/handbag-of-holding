[CmdletBinding(SupportsShouldProcess = $true)]
param(
    [string]$Root,
    [switch]$AllWorkspaces,
    [switch]$IncludeEditor,
    [switch]$SkipProcessStop,
    [switch]$SkipEnvironmentCleanup
)

Set-StrictMode -Version 3.0
$ErrorActionPreference = "Stop"

function Resolve-UnrealRoot {
    param([string]$RequestedRoot)

    if (-not [string]::IsNullOrWhiteSpace($RequestedRoot)) {
        return (Resolve-Path -LiteralPath $RequestedRoot).Path.TrimEnd("\")
    }

    $here = (Resolve-Path ".").Path
    while ($here) {
        if (Test-Path -LiteralPath (Join-Path $here "Engine\Build\BatchFiles\Build.bat")) {
            return $here.TrimEnd("\")
        }

        $childRoot = Join-Path $here "root"
        if (Test-Path -LiteralPath (Join-Path $childRoot "Engine\Build\BatchFiles\Build.bat")) {
            return $childRoot.TrimEnd("\")
        }

        $parent = Split-Path $here -Parent
        if ($parent -eq $here) {
            break
        }
        $here = $parent
    }

    return $null
}

function Test-RootMatch {
    param(
        [string]$CommandLine,
        [string]$ResolvedRoot
    )

    if ($AllWorkspaces -or [string]::IsNullOrWhiteSpace($ResolvedRoot)) {
        return $true
    }

    return $CommandLine.ToLowerInvariant().Contains($ResolvedRoot.ToLowerInvariant())
}

function Get-ShortCommandLine {
    param([string]$CommandLine)

    if ([string]::IsNullOrWhiteSpace($CommandLine)) {
        return ""
    }
    if ($CommandLine.Length -le 220) {
        return $CommandLine
    }
    return $CommandLine.Substring(0, 220) + "..."
}

function Test-UnrealBuildSeed {
    param(
        [object]$Process,
        [string]$ResolvedRoot
    )

    $name = [string]$Process.Name
    $commandLine = [string]$Process.CommandLine

    if ([string]::IsNullOrWhiteSpace($commandLine)) {
        return $false
    }
    if (-not (Test-RootMatch -CommandLine $commandLine -ResolvedRoot $ResolvedRoot)) {
        return $false
    }

    if ($name -ieq "cmd.exe" -and $commandLine -match "(Build|RunUAT|GenerateProjectFiles)\.bat") {
        return $true
    }
    if ($name -ieq "dotnet.exe" -and $commandLine -match "(UnrealBuildTool|AutomationTool|MSBuild\.dll)") {
        return $true
    }
    if ($name -ieq "UnrealBuildTool.exe") {
        return $true
    }
    if ($name -match "^Uba.*\.exe$") {
        return $true
    }
    if ($name -match "^(cl|link|rc|cvtres|mspdbsrv|msbuild|vbcscompiler)\.exe$") {
        return $true
    }
    if ($IncludeEditor -and $name -match "^Unreal(Editor|Game|Client|Server).*.exe$") {
        return $true
    }

    return $false
}

function Add-ProcessTree {
    param(
        [uint32]$ProcessId,
        [hashtable]$AllByParent,
        [object[]]$AllProcesses,
        [hashtable]$Targets
    )

    if ($Targets.ContainsKey([string]$ProcessId)) {
        return
    }

    $process = $AllProcesses | Where-Object { $_.ProcessId -eq $ProcessId } | Select-Object -First 1
    if (-not $process) {
        return
    }

    $Targets[[string]$ProcessId] = $process
    $children = $AllByParent[[string]$ProcessId]
    if ($children) {
        foreach ($child in $children) {
            Add-ProcessTree -ProcessId ([uint32]$child.ProcessId) -AllByParent $AllByParent -AllProcesses $AllProcesses -Targets $Targets
        }
    }
}

function Stop-UnrealBuildProcesses {
    param([string]$ResolvedRoot)

    $allProcesses = @(Get-CimInstance Win32_Process)
    $byParent = $allProcesses | Group-Object ParentProcessId -AsHashTable -AsString
    $seeds = @($allProcesses | Where-Object { Test-UnrealBuildSeed -Process $_ -ResolvedRoot $ResolvedRoot })
    $targets = @{}

    foreach ($seed in $seeds) {
        Add-ProcessTree -ProcessId ([uint32]$seed.ProcessId) -AllByParent $byParent -AllProcesses $allProcesses -Targets $targets
    }

    $orderedTargets = @($targets.Values | Sort-Object ProcessId -Descending)

    if ($orderedTargets.Count -eq 0) {
        Write-Host "No matching Unreal build processes found."
        return
    }

    Write-Host "Found $($orderedTargets.Count) Unreal build process(es) to stop:"
    $orderedTargets |
        Select-Object ProcessId, ParentProcessId, Name, @{Name = "CommandLine"; Expression = { Get-ShortCommandLine $_.CommandLine }} |
        Format-Table -AutoSize

    foreach ($process in $orderedTargets) {
        $label = "$($process.Name) ($($process.ProcessId))"
        if ($PSCmdlet.ShouldProcess($label, "Stop process")) {
            try {
                Stop-Process -Id $process.ProcessId -Force -ErrorAction Stop
                Write-Host "Stopped $label"
            }
            catch {
                Write-Warning "Could not stop $label`: $($_.Exception.Message)"
            }
        }
    }
}

function Clear-UnrealBuildEnvironment {
    $exactNames = @(
        "VisualStudioDir",
        "VSSKUEDITION",
        "PkgDefApplicationConfigFile",
        "VSAPPIDDIR",
        "VisualStudioEdition",
        "VisualStudioVersion",
        "DOTNET_ROOT",
        "DOTNET_ROOT(x86)",
        "MSBuildSDKsPath",
        "MSBuildExtensionsPath",
        "MSBUILD_EXE_PATH",
        "FrameworkDir",
        "FrameworkDIR64",
        "FrameworkVersion",
        "FrameworkVersion64",
        "WindowsSDKDir",
        "WindowsSDKVersion"
    )

    $removed = New-Object System.Collections.Generic.List[string]

    foreach ($name in $exactNames) {
        $path = "Env:\$name"
        if (Test-Path -LiteralPath $path) {
            if ($PSCmdlet.ShouldProcess($path, "Remove environment variable")) {
                Remove-Item -LiteralPath $path -ErrorAction SilentlyContinue
                $removed.Add($name)
            }
        }
    }

    $patterned = @(Get-ChildItem Env: | Where-Object { $_.Name -like "uebp_*" -or $_.Name -like "UAT_*" })
    foreach ($item in $patterned) {
        $path = "Env:\$($item.Name)"
        if ($PSCmdlet.ShouldProcess($path, "Remove environment variable")) {
            Remove-Item -LiteralPath $path -ErrorAction SilentlyContinue
            $removed.Add($item.Name)
        }
    }

    if ($PSCmdlet.ShouldProcess("Env:\MSBUILDDISABLENODEREUSE", "Set to 1")) {
        $env:MSBUILDDISABLENODEREUSE = "1"
    }

    if ($removed.Count -eq 0) {
        Write-Host "No stale Visual Studio/MSBuild/.NET/UAT environment variables were present."
    }
    else {
        Write-Host "Removed environment variables:"
        $removed | Sort-Object | ForEach-Object { Write-Host "  $_" }
    }

    Write-Host "Set MSBUILDDISABLENODEREUSE=1"
}

$resolvedRoot = Resolve-UnrealRoot -RequestedRoot $Root
if ($resolvedRoot) {
    Write-Host "Unreal root: $resolvedRoot"
}
else {
    Write-Warning "No Unreal root was resolved. Process matching will use clearly Unreal build-tool command lines only."
}

if (-not $SkipProcessStop) {
    Stop-UnrealBuildProcesses -ResolvedRoot $resolvedRoot
}
else {
    Write-Host "Skipping process stop."
}

if (-not $SkipEnvironmentCleanup) {
    Clear-UnrealBuildEnvironment
}
else {
    Write-Host "Skipping environment cleanup."
}
