# Read-only preservation and catalog verification. Requires Python, PyYAML and Markdown.
python -B (Join-Path $PSScriptRoot 'verify_recovery.py') @args
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
