# The original schema verifier is preserved in verify-initial-migration.ps1.historical.
# Run the current recovery/preservation checks from any working directory.
& (Join-Path $PSScriptRoot '../2026-10-13-spec-recovery/verify-recovery.ps1')
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
