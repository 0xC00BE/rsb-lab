[CmdletBinding(SupportsShouldProcess)]
param(
    [string]$ExpectedComputerName = 'RSB-WS03',
    [string]$ServiceName          = 'RSBEngineeringAgent',
    [string]$ServiceAccountName   = 'svc_engagent',
    [securestring]$ServiceAccountPassword,
    [string]$Broker               = '10.0.20.21',
    [int]$Port                    = 1883,
    [string]$BrokerUser           = 'rsb_broker',
    [string]$BrokerPassword,
    [string]$TopicBase            = 'rsb/eng/ws03',
    [string]$SourceFile           = (Join-Path $PSScriptRoot 'RSBEngineeringAgent.cs'),
    [switch]$ForceComputerName
)

# Lab-only installer for the RSB Engineering Agent on the DMZ jump host.
# Compiles the in-box .NET Framework service (no NuGet/internet), creates a
# low-privilege service account, installs/starts the service, and records a
# baseline for rollback. Run from an elevated Windows PowerShell 5.1 session.

$ErrorActionPreference = 'Stop'
$installRoot = 'C:\ProgramData\RSB-Lab\EngAgent'
$binaryPath  = Join-Path $installRoot 'RSBEngineeringAgent.exe'
$configPath  = Join-Path $installRoot 'agent.config'
$baselinePath= Join-Path $installRoot 'baseline.json'

if ($PSVersionTable.PSEdition -ne 'Desktop') {
    throw 'Run with Windows PowerShell 5.1 (powershell.exe); its Add-Type compiler builds the .NET Framework service exe.'
}
$admin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole(
    [Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $admin) { throw 'Run this script from an elevated Windows PowerShell session.' }
if (-not $ForceComputerName -and $env:COMPUTERNAME -ne $ExpectedComputerName) {
    throw "Intended for $ExpectedComputerName but running on $env:COMPUTERNAME. Use -ForceComputerName for an intentional clone."
}
if (-not (Test-Path -LiteralPath $SourceFile)) { throw "Source file not found: $SourceFile" }
if (-not $BrokerPassword) {
    $sec = Read-Host "Enter the MQTT broker password for $BrokerUser" -AsSecureString
    $BrokerPassword = [Runtime.InteropServices.Marshal]::PtrToStringAuto(
        [Runtime.InteropServices.Marshal]::SecureStringToBSTR($sec))
}
if (-not $ServiceAccountPassword) {
    $ServiceAccountPassword = Read-Host "Enter the lab-only password for .\$ServiceAccountName" -AsSecureString
}

New-Item -ItemType Directory -Path $installRoot -Force | Out-Null

# Baseline for rollback (captured once).
if (-not (Test-Path -LiteralPath $baselinePath)) {
    [pscustomobject]@{
        CapturedAt    = (Get-Date).ToString('o')
        Computer      = $env:COMPUTERNAME
        ExistingSvc   = [bool](Get-Service -Name $ServiceName -ErrorAction SilentlyContinue)
        ExistingUser  = [bool](Get-LocalUser -Name $ServiceAccountName -ErrorAction SilentlyContinue)
    } | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath $baselinePath -Encoding UTF8
}

# Low-privilege local service account.
$localUser = Get-LocalUser -Name $ServiceAccountName -ErrorAction SilentlyContinue
if (-not $localUser) {
    New-LocalUser -Name $ServiceAccountName -Password $ServiceAccountPassword `
        -Description 'RSB lab engineering agent (low priv)' `
        -AccountNeverExpires -PasswordNeverExpires | Out-Null
} else {
    Set-LocalUser -Name $ServiceAccountName -Password $ServiceAccountPassword -PasswordNeverExpires $true
}
Enable-LocalUser -Name $ServiceAccountName
$localUser = Get-LocalUser -Name $ServiceAccountName

function Grant-LogOnAsService {
    param([string]$AccountSid)
    $cfg = Join-Path $env:TEMP "rsb-secpol-$([guid]::NewGuid().ToString('N')).inf"
    $db  = Join-Path $env:TEMP "rsb-secpol-$([guid]::NewGuid().ToString('N')).sdb"
    try {
        & secedit.exe /export /cfg $cfg /areas USER_RIGHTS /quiet | Out-Null
        $lines = [Collections.Generic.List[string]](Get-Content -LiteralPath $cfg)
        $index = -1
        for ($i = 0; $i -lt $lines.Count; $i++) { if ($lines[$i] -match '^SeServiceLogonRight\s*=') { $index = $i; break } }
        $sidToken = "*$AccountSid"
        if ($index -ge 0) {
            $members = @((($lines[$index] -split '=',2)[1].Trim() -split ',') | Where-Object { $_ })
            if ($members -notcontains $sidToken) { $members += $sidToken }
            $lines[$index] = 'SeServiceLogonRight = ' + ($members -join ',')
        } else {
            $pi = $lines.IndexOf('[Privilege Rights]')
            if ($pi -lt 0) { throw 'No [Privilege Rights] section in exported policy.' }
            $lines.Insert($pi + 1, "SeServiceLogonRight = $sidToken")
        }
        Set-Content -LiteralPath $cfg -Value $lines -Encoding Unicode
        & secedit.exe /configure /db $db /cfg $cfg /areas USER_RIGHTS /quiet | Out-Null
    } finally { Remove-Item -LiteralPath $cfg, $db -Force -ErrorAction SilentlyContinue }
}
Grant-LogOnAsService -AccountSid $localUser.SID.Value

# Agent configuration (broker endpoint + credentials + topics).
@(
    "broker=$Broker"
    "port=$Port"
    "user=$BrokerUser"
    "password=$BrokerPassword"
    "topic_base=$TopicBase"
    "client_id=ws03-engagent"
) | Set-Content -LiteralPath $configPath -Encoding ASCII

# Compile the service exe from source with the in-box compiler.
if (Get-Service -Name $ServiceName -ErrorAction SilentlyContinue) {
    Stop-Service -Name $ServiceName -Force -ErrorAction SilentlyContinue
    & sc.exe delete $ServiceName | Out-Null
    Start-Sleep -Seconds 2
}
$src = Get-Content -Raw -LiteralPath $SourceFile
Add-Type -TypeDefinition $src -OutputAssembly $binaryPath -OutputType ConsoleApplication `
    -ReferencedAssemblies 'System.ServiceProcess.dll', 'System.Web.Extensions.dll'
if (-not (Test-Path -LiteralPath $binaryPath)) { throw 'Compilation did not produce the service executable.' }

# Defender: scoped exclusion for the agent binary only (deliberate lab weakness).
try {
    Add-MpPreference -ExclusionPath $binaryPath -ErrorAction Stop
    Write-Host "Added Defender exclusion for $binaryPath"
} catch { Write-Warning "Could not add Defender exclusion (continuing): $($_.Exception.Message)" }

# Install and start the service under the low-privilege account.
$cred = New-Object System.Management.Automation.PSCredential(
    ".\$ServiceAccountName", $ServiceAccountPassword)
New-Service -Name $ServiceName -BinaryPathName $binaryPath `
    -DisplayName 'RSB Engineering Agent' -StartupType Automatic -Credential $cred | Out-Null
Start-Service -Name $ServiceName

Start-Sleep -Seconds 3
$svc = Get-Service -Name $ServiceName
Write-Host "Service '$ServiceName' status: $($svc.Status), account: .\$ServiceAccountName"
Write-Host "Agent log: $installRoot\agent.log"
