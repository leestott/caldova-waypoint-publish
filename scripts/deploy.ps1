param([switch]$Provision)
$ErrorActionPreference = 'Stop'
if (-not $Provision) {
    throw 'This creates billable Azure resources and tenant objects. Configure your .env, then pass -Provision explicitly.'
}
Push-Location (Join-Path $PSScriptRoot '..')
try {
    $python = Join-Path (Get-Location) '.venv\Scripts\python.exe'
    if (-not (Test-Path -LiteralPath $python)) { throw 'Run scripts\setup.ps1 first.' }
    $steps = @(
        @('scripts\deploy_azure.py', 'bootstrap'),
        @('scripts\deploy_azure.py', 'identity'),
        @('scripts\deploy_azure.py', 'finance'),
        @('scripts\deploy_container.py', 'infrastructure'),
        @('scripts\deploy_container.py', 'build'),
        @('scripts\deploy_container.py', 'configure'),
        @('scripts\deploy_azure.py', 'bot'),
        @('scripts\deploy_azure.py', 'package', '--compatibility'),
        @('scripts\deploy_workflow.py')
    )
    foreach ($step in $steps) {
        & $python @step
        if ($LASTEXITCODE -ne 0) { throw "Deployment stopped at $($step[0]); inspect saved state before retrying." }
    }
    Write-Output 'Infrastructure and package prepared. Complete connector authorization, app submission and pilot scoping using docs\TENANT-SETUP.md.'
} finally {
    Pop-Location
}
