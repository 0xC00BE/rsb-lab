[CmdletBinding(SupportsShouldProcess)]
param(
    [string]$ServiceName        = 'RSBEngineeringAgent',
    [string]$ServiceAccountName = 'svc_engagent',
    [switch]$KeepAccount
)

# Teardown for the RSB Engineering Agent. Removes the service, Defender
# exclusion, binary/config, and (unless -KeepAccount) the local service account.

$ErrorActionPreference = 'Stop'
$installRoot = 'C:\ProgramData\RSB-Lab\EngAgent'
$binaryPath  = Join-Path $installRoot 'RSBEngineeringAgent.exe'

$admin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole(
    [Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $admin) { throw 'Run this script from an elevated Windows PowerShell session.' }

if (Get-Service -Name $ServiceName -ErrorAction SilentlyContinue) {
    Stop-Service -Name $ServiceName -Force -ErrorAction SilentlyContinue
    & sc.exe delete $ServiceName | Out-Null
    Write-Host "Removed service $ServiceName"
}
try { Remove-MpPreference -ExclusionPath $binaryPath -ErrorAction Stop; Write-Host 'Removed Defender exclusion' } catch {}
Remove-Item -LiteralPath $binaryPath -Force -ErrorAction SilentlyContinue
Remove-Item -LiteralPath (Join-Path $installRoot 'agent.config') -Force -ErrorAction SilentlyContinue

if (-not $KeepAccount -and (Get-LocalUser -Name $ServiceAccountName -ErrorAction SilentlyContinue)) {
    Remove-LocalUser -Name $ServiceAccountName
    Write-Host "Removed local account $ServiceAccountName"
}
Write-Host 'Teardown complete. agent.log and baseline.json retained for review.'
