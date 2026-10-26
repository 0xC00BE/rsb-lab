param(
    [Parameter(Mandatory)]
    [ValidateSet('Jump','Engineering')]
    [string]$Role
)

$ErrorActionPreference = 'Stop'
$domainNetBIOS = 'RS'
$changeLog = [System.Collections.Generic.List[string]]::new()
Start-Transcript -LiteralPath 'C:\Windows\Temp\RSB-Configure.log' -Force | Out-Null

function Add-Change([string]$Message) { $changeLog.Add($Message) }

function Ensure-FirewallRule {
    param(
        [string]$Name,
        [int]$Port,
        [string[]]$RemoteAddress
    )
    $existing = Get-NetFirewallRule -Name $Name -ErrorAction SilentlyContinue
    if ($existing) { Remove-NetFirewallRule -Name $Name }
    New-NetFirewallRule -Name $Name -DisplayName $Name -Group 'RSB ICS Lab' `
        -Direction Inbound -Action Allow -Enabled True -Profile Any `
        -Protocol TCP -LocalPort $Port -RemoteAddress $RemoteAddress | Out-Null
    Add-Change "Staged firewall rule $Name TCP/$Port from $($RemoteAddress -join ',')"
}

# Enable RDP with NLA and strong transport settings. The broad built-in RDP
# firewall group is disabled; narrowly scoped custom rules are staged below.
Set-ItemProperty -LiteralPath 'HKLM:\SYSTEM\CurrentControlSet\Control\Terminal Server' `
    -Name fDenyTSConnections -Type DWord -Value 0
Set-ItemProperty -LiteralPath 'HKLM:\SYSTEM\CurrentControlSet\Control\Terminal Server\WinStations\RDP-Tcp' `
    -Name UserAuthentication -Type DWord -Value 1
Set-ItemProperty -LiteralPath 'HKLM:\SYSTEM\CurrentControlSet\Control\Terminal Server\WinStations\RDP-Tcp' `
    -Name SecurityLayer -Type DWord -Value 2
Set-ItemProperty -LiteralPath 'HKLM:\SYSTEM\CurrentControlSet\Control\Terminal Server\WinStations\RDP-Tcp' `
    -Name MinEncryptionLevel -Type DWord -Value 3
Set-Service -Name TermService -StartupType Automatic
Start-Service -Name TermService
Get-NetFirewallRule -DisplayGroup 'Remote Desktop' -ErrorAction SilentlyContinue |
    Disable-NetFirewallRule -ErrorAction SilentlyContinue
Add-Change 'Enabled Remote Desktop with NLA; disabled broad built-in RDP firewall rules'

# Enable WinRM for the VPN management client, but replace its broad firewall
# rules with a rule limited to the single OpenVPN administration address.
Enable-PSRemoting -Force -SkipNetworkProfileCheck
Get-NetFirewallRule -DisplayGroup 'Windows Remote Management' -ErrorAction SilentlyContinue |
    Disable-NetFirewallRule -ErrorAction SilentlyContinue
Ensure-FirewallRule -Name 'RSB-MGMT-WinRM-HTTP' -Port 5985 -RemoteAddress @('10.0.10.254')
Ensure-FirewallRule -Name 'RSB-MGMT-SMB' -Port 445 -RemoteAddress @('10.0.10.254')

if ($Role -eq 'Jump') {
    $allowedGroup = "$domainNetBIOS\RSB-Jump-RDP"
    Ensure-FirewallRule -Name 'RSB-JUMP-RDP' -Port 3389 -RemoteAddress @('10.0.10.0/24','10.0.10.254')

    $legacyRoot = 'C:\RSB-Lab\LegacyConnections'
    New-Item -ItemType Directory -Path $legacyRoot -Force | Out-Null
    @'
screen mode id:i:2
use multimon:i:0
desktopwidth:i:1440
desktopheight:i:900
session bpp:i:32
full address:s:10.0.40.12
prompt for credentials:i:1
authentication level:i:2
username:s:RS\henrik.solberg
'@ | Set-Content -LiteralPath (Join-Path $legacyRoot 'RSB-Engineering.rdp') -Encoding ASCII
    @'
@echo off
REM Legacy brewery expansion support helper. Pending migration to the vault.
cmdkey /generic:TERMSRV/10.0.40.12 /user:RS\henrik.solberg /pass:PublicLab!User02
mstsc.exe C:\RSB-Lab\LegacyConnections\RSB-Engineering.rdp
'@ | Set-Content -LiteralPath (Join-Path $legacyRoot 'connect-engineering.cmd') -Encoding ASCII
    & icacls.exe $legacyRoot /inheritance:r /grant:r `
        'BUILTIN\Administrators:(OI)(CI)(F)' 'SYSTEM:(OI)(CI)(F)' `
        "$domainNetBIOS\RSB-Jump-RDP:(OI)(CI)(RX)" | Out-Null
    Add-Change 'Created restricted legacy engineering connection material for controlled Path 2'
} else {
    $allowedGroup = "$domainNetBIOS\RSB-Engineering-RDP"
    Ensure-FirewallRule -Name 'RSB-ENG-RDP' -Port 3389 -RemoteAddress @('10.0.20.11','10.0.10.254')

    $engineeringRoot = 'C:\RSB-Lab\Engineering'
    New-Item -ItemType Directory -Path $engineeringRoot -Force | Out-Null
    @'
RSB OT engineering endpoints

FUXA HMI:       http://10.0.40.10:1881/
Scada-LTS:      http://10.0.40.20:8080/Scada-LTS/
Grafana:        http://10.0.30.30:3000/
OpenPLC cells:  http://10.0.50.101:8080/ through http://10.0.50.106:8080/
Modbus TCP:     10.0.50.101-10.0.50.106, TCP/502

Use the approved RSB register map before issuing process writes.
'@ | Set-Content -LiteralPath (Join-Path $engineeringRoot 'OT-ENDPOINTS.txt') -Encoding UTF8
    & icacls.exe $engineeringRoot /inheritance:r /grant:r `
        'BUILTIN\Administrators:(OI)(CI)(F)' 'SYSTEM:(OI)(CI)(F)' `
        "$domainNetBIOS\RSB-Engineering-RDP:(OI)(CI)(RX)" | Out-Null
    Add-Change 'Created OT engineering endpoint reference'
}

$rdpGroup = Get-LocalGroup -SID 'S-1-5-32-555'
if (-not (Get-LocalGroupMember -Group $rdpGroup.Name -ErrorAction SilentlyContinue |
        Where-Object Name -eq $allowedGroup)) {
    Add-LocalGroupMember -Group $rdpGroup.Name -Member $allowedGroup
    Add-Change "Added $allowedGroup to local Remote Desktop Users"
}

# Native audit coverage. Sysmon installation is tracked separately because the
# corporate workstation is offline and all three hosts should use one package.
foreach ($subcategory in @('Logon','Logoff','User Account Management','Security Group Management','Process Creation','File Share','Other Object Access Events')) {
    & auditpol.exe /set /subcategory:"$subcategory" /success:enable /failure:enable | Out-Null
}
New-Item -ItemType Directory -Path 'C:\ProgramData\RSB\Transcripts' -Force | Out-Null
Add-Change 'Enabled native logon, account/group, process, file-share, and object-access auditing'

# Apply the already-linked OU GPO immediately. This does not enable Windows
# Firewall profiles; it only receives logging and RDP security policy.
& gpupdate.exe /target:computer /force | Out-Null

[pscustomobject]@{
    Computer = $env:COMPUTERNAME
    Role = $Role
    FirewallProfiles = Get-NetFirewallProfile | Select-Object Name,Enabled
    RemoteDesktopGroup = $allowedGroup
    RdpListening = [bool](Get-NetTCPConnection -LocalPort 3389 -State Listen -ErrorAction SilentlyContinue)
    WinRMService = (Get-Service WinRM).Status.ToString()
    Changes = $changeLog
} | ConvertTo-Json -Depth 5
Stop-Transcript | Out-Null
