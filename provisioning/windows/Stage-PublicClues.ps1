#requires -RunAsAdministrator
[CmdletBinding()]
param([Parameter(Mandatory)][ValidateSet('Corporate','Jump')][string]$Role)
$ErrorActionPreference = 'Stop'
$accountsPath = Join-Path $PSScriptRoot '../../lab/public-training-accounts.json'
$accounts = (Get-Content -Raw -LiteralPath $accountsPath | ConvertFrom-Json).accounts
if ($Role -eq 'Corporate') {
    if ($env:COMPUTERNAME -ne 'RSB-WS01') { throw 'Run Corporate on RSB-WS01.' }
    $path = 'C:\RSB-Lab\LegacyWebApp'
    New-Item -ItemType Directory -Force -Path $path | Out-Null
    $password = ($accounts | Where-Object account -eq 'sara.nilsen').password
    @{ app = 'Brewery expansion'; username = 'RS\sara.nilsen'; password = $password } |
        ConvertTo-Json | Set-Content -LiteralPath (Join-Path $path 'appsettings.json')
    & icacls.exe $path /inheritance:r /grant:r 'SYSTEM:(OI)(CI)(F)' `
        'BUILTIN\Administrators:(OI)(CI)(F)' 'BUILTIN\Users:(OI)(CI)(RX)' | Out-Null
} else {
    if ($env:COMPUTERNAME -ne 'RSB-WS03') { throw 'Run Jump on RSB-WS03.' }
    $path = 'C:\RSB-Lab\EngineeringHandoff'
    New-Item -ItemType Directory -Force -Path $path | Out-Null
    $password = ($accounts | Where-Object account -eq 'henrik.solberg').password
    "Engineering workstation: 10.0.40.12`r`nUsername: RS\henrik.solberg`r`nPassword: $password" |
        Set-Content -LiteralPath (Join-Path $path 'Engineering-Handoff.txt')
    & icacls.exe $path /inheritance:r /grant:r 'SYSTEM:(OI)(CI)(F)' `
        'BUILTIN\Administrators:(OI)(CI)(F)' | Out-Null
}
Write-Host 'Staged public exercise clues. These are deliberately exposed training credentials.'
