[CmdletBinding()]
param(
    [string]$ServiceName        = 'RSBEngineeringAgent',
    [string]$ServiceAccountName = 'svc_engagent'
)

$ErrorActionPreference = 'Stop'
$installRoot = 'C:\ProgramData\RSB-Lab\EngAgent'
$svc = Get-CimInstance Win32_Service -Filter "Name='$ServiceName'" -ErrorAction SilentlyContinue
$acct = Get-LocalUser -Name $ServiceAccountName -ErrorAction SilentlyContinue

[pscustomobject]@{
    Computer         = $env:COMPUTERNAME
    ServiceInstalled = [bool]$svc
    ServiceState     = $svc.State
    ServiceStartMode = $svc.StartMode
    ServiceStartName = $svc.StartName
    AccountExists    = [bool]$acct
    AccountEnabled   = $acct.Enabled
    BinaryExists     = Test-Path -LiteralPath (Join-Path $installRoot 'RSBEngineeringAgent.exe')
    ConfigExists     = Test-Path -LiteralPath (Join-Path $installRoot 'agent.config')
    DefenderExclusion= [bool]((Get-MpPreference -ErrorAction SilentlyContinue).ExclusionPath `
                        -contains (Join-Path $installRoot 'RSBEngineeringAgent.exe'))
    RecentLog        = @(Get-Content -LiteralPath (Join-Path $installRoot 'agent.log') -Tail 6 -ErrorAction SilentlyContinue | ForEach-Object { $_.ToString() })
} | ConvertTo-Json -Depth 5
