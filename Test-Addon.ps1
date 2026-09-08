[CmdletBinding()]
param(
    [ValidateSet('Setup', 'Bootstrap', 'Doctor', 'Configure', 'Static', 'Game', 'All')]
    [string]$Mode = 'All',
    [string]$World,
    [string]$LogDirectory,
    [string]$Python = 'python'
)

$ErrorActionPreference = 'Stop'
$testPython = Join-Path $PSScriptRoot '.venv-testing\Scripts\python.exe'
try {
    if ($Mode -in @('Setup', 'Bootstrap', 'All', 'Game') -or -not (Test-Path -LiteralPath $testPython)) {
        if (-not (Test-Path -LiteralPath $testPython)) {
            & $Python -m venv (Join-Path $PSScriptRoot '.venv-testing')
            if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
        }
        & $testPython -m pip install -r (Join-Path $PSScriptRoot 'requirements-testing.txt')
        if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
        if ($Mode -eq 'Setup') { $Mode = 'Bootstrap' }
    }
    if (-not (Test-Path -LiteralPath $testPython)) {
        throw 'Run .\Test-Addon.ps1 -Mode Setup first (Python 3.11+ required).'
    }
    $runnerArguments = @((Join-Path $PSScriptRoot 'scripts\bedrock_test.py'), $Mode.ToLowerInvariant())
    if ($World) { $runnerArguments += @('--world', $World) }
    if ($LogDirectory) { $runnerArguments += @('--log-directory', $LogDirectory) }
    & $testPython @runnerArguments
    exit $LASTEXITCODE
} catch {
    Write-Error -Message $_ -ErrorAction Continue
    exit 2
}
