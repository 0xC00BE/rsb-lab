#requires -RunAsAdministrator
[CmdletBinding()]
param(
    [Parameter(Mandatory)][ValidateSet('AD','Corporate','Jump','Engineering')][string]$Role,
    [securestring]$ServiceAccountPassword,
    [securestring]$BrokerPassword,
    [switch]$EnableVpn
)
$ErrorActionPreference='Stop'
if ($PSVersionTable.PSEdition -ne 'Desktop') {throw 'Run with Windows PowerShell 5.1.'}
$expected=@{AD='RSBAD01';Corporate='RSB-WS01';Jump='RSB-WS03';Engineering='RSB-WS02'}
if ($env:COMPUTERNAME -ne $expected[$Role]) {throw 'The selected role does not match this computer.'}
if ((Get-CimInstance Win32_ComputerSystem).Domain -ne 'rs.brew') {throw 'Create or join rs.brew before installing a role.'}
$logRoot='C:\ProgramData\RSB-Lab\Setup'
New-Item -ItemType Directory -Force -Path $logRoot | Out-Null
& icacls.exe $logRoot /inheritance:r /grant:r 'SYSTEM:(OI)(CI)(F)' 'BUILTIN\Administrators:(OI)(CI)(F)' | Out-Null
if ($LASTEXITCODE -ne 0) {throw 'Could not protect the setup logs.'}
function Invoke-SetupStep([string]$Name,[string]$Script,[hashtable]$Arguments=@{}) {
    $log=Join-Path $logRoot ($Name+'.log')
    try { & (Join-Path $PSScriptRoot $Script) @Arguments *> $log }
    catch {throw "Setup step $Name failed. Review the private log at $log."}
    Write-Host "Completed setup step: $Name"
}
if ($Role -eq 'AD') {
    Invoke-SetupStep 'directory' 'Implement-RSBAD.ps1'
    Invoke-SetupStep 'domain-policy' 'Configure-RSBReachabilityAndNTLM-GPO.ps1'
    Invoke-SetupStep 'workstation-policy' 'Configure-RSBResponderChallengeGPO.ps1'
} elseif ($Role -eq 'Corporate') {
    Invoke-SetupStep 'corporate-content' 'Stage-PublicClues.ps1' @{Role='Corporate'}
    $trainingPassword=ConvertTo-SecureString 'Password1!' -AsPlainText -Force
    Invoke-SetupStep 'corporate-service' 'Install-RSBResponderChallenge.ps1' @{ServiceAccountPassword=$trainingPassword}
} else {
    Invoke-SetupStep 'workstation' 'Configure-RSBWorkstation.ps1' @{Role=$Role}
    if ($Role -eq 'Jump') {
        if (-not $ServiceAccountPassword) {$ServiceAccountPassword=Read-Host 'Choose a private local service-account password' -AsSecureString}
        if (-not $BrokerPassword) {$BrokerPassword=Read-Host 'Enter MQTT_PASSWORD from the Docker guest .env' -AsSecureString}
        Invoke-SetupStep 'jump-content' 'Stage-PublicClues.ps1' @{Role='Jump'}
        $pointer=[Runtime.InteropServices.Marshal]::SecureStringToBSTR($BrokerPassword)
        try {
            $plain=[Runtime.InteropServices.Marshal]::PtrToStringBSTR($pointer)
            Invoke-SetupStep 'jump-service' 'mqtt-agent/Install-RSBEngineeringAgent.ps1' @{
                ServiceAccountPassword=$ServiceAccountPassword;BrokerPassword=$plain}
        } finally {$plain=$null;[Runtime.InteropServices.Marshal]::ZeroFreeBSTR($pointer)}
        Invoke-SetupStep 'jump-maintenance' 'Install-RSBMaintenance.ps1'
    }
}
Invoke-SetupStep 'host-firewall' 'Stage-RSBFirewallRules.ps1' @{Role=$Role}
Set-NetFirewallProfile -Profile Domain,Private,Public -Enabled True
if($EnableVpn){Invoke-SetupStep 'vpn-management' 'Configure-RSBVpnAccess.ps1' @{Role=$Role}}
Write-Host "Installed $Role on $env:COMPUTERNAME. Reboot members after domain policy application."
