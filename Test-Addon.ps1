[CmdletBinding()]
param(
    [ValidateSet('Setup', 'Bootstrap', 'Doctor', 'Configure', 'Static', 'Scenarios', 'Game', 'Client', 'All')]
    [string]$Mode = 'All',
    [string]$World,
    [string]$LogDirectory,
    [string]$Only,
    [switch]$Trace,
    [string]$Diag,
    [string]$Python = 'python'
)

$ErrorActionPreference = 'Stop'
$testPython = Join-Path $PSScriptRoot '.venv-testing\Scripts\python.exe'
try {
    if ($Mode -in @('Setup', 'Bootstrap', 'All', 'Game', 'Client') -or -not (Test-Path -LiteralPath $testPython)) {
        if (-not (Test-Path -LiteralPath $testPython)) {
            & $Python -m venv (Join-Path $PSScriptRoot '.venv-testing')
            if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
        }
        & $testPython -m pip install -q -r (Join-Path $PSScriptRoot 'requirements-testing.txt')
        if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
        if ($Mode -eq 'Setup') { $Mode = 'Bootstrap' }
    }
    if (-not (Test-Path -LiteralPath $testPython)) {
        throw 'Run .\Test-Addon.ps1 -Mode Setup first (Python 3.11+ required).'
    }
    if ($Mode -in @('Bootstrap', 'Static', 'All')) {
        # Dev tooling for the Script API type check, and the pre-commit guardrail.
        if (-not (Test-Path -LiteralPath (Join-Path $PSScriptRoot 'node_modules'))) {
            Push-Location $PSScriptRoot
            try { npm ci --silent } finally { Pop-Location }
            if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
        }
        git -C $PSScriptRoot config core.hooksPath .githooks
    }
    if ($Mode -in @('Static', 'All')) {
        & (Join-Path $PSScriptRoot 'node_modules\.bin\tsc.cmd') -p (Join-Path $PSScriptRoot 'jsconfig.json')
        if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    }
    $runnerArguments = @((Join-Path $PSScriptRoot 'scripts\bedrock_test.py'), $Mode.ToLowerInvariant())
    if ($World) { $runnerArguments += @('--world', $World) }
    if ($LogDirectory) { $runnerArguments += @('--log-directory', $LogDirectory) }
    if ($Only) { $runnerArguments += @('--only', $Only) }
    if ($Trace) { $runnerArguments += '--trace' }
    if ($Diag) { $runnerArguments += @('--diag', $Diag) }
    & $testPython @runnerArguments
    exit $LASTEXITCODE
} catch {
    Write-Error -Message $_ -ErrorAction Continue
    exit 2
}
