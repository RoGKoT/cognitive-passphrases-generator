# PowerShell wrapper: run generator from the repo directory with same python that is installed
$here = Split-Path -Parent $MyInvocation.MyCommand.Definition
Set-Location $here
try {
    python .\generate_passphrase.py @args
} catch {
    Write-Host 'python not found, trying py launcher...'
    py .\generate_passphrase.py @args
}
