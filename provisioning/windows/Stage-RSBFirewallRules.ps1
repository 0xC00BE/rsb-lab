param(
    [Parameter(Mandatory)]
    [ValidateSet('AD','Corporate','Jump','Engineering')]
    [string]$Role
)

$ErrorActionPreference = 'Stop'
$group = 'RSB ICS Lab'
$staged = [System.Collections.Generic.List[string]]::new()

function Ensure-RsbRule {
    param(
        [string]$Name,
        [ValidateSet('Inbound','Outbound')][string]$Direction,
        [string]$Protocol = 'TCP',
        [string]$LocalPort = 'Any',
        [string]$RemotePort = 'Any',
        [string[]]$RemoteAddress = @('Any')
    )
    if (-not (Get-NetFirewallRule -Name $Name -ErrorAction SilentlyContinue)) {
        $params = @{
            Name = $Name; DisplayName = $Name; Group = $group; Direction = $Direction
            Action = 'Allow'; Enabled = 'True'; Profile = 'Any'; Protocol = $Protocol
            RemoteAddress = $RemoteAddress
        }
        if ($Protocol -notlike 'ICMP*') {
            $params.LocalPort = $LocalPort
            $params.RemotePort = $RemotePort
        }
        New-NetFirewallRule @params | Out-Null
        $staged.Add($Name)
    }
}

# These are additions only.  The script deliberately does not change firewall
# profile state, default actions, RDP registry state, or existing rules.
if ($Role -eq 'AD') {
    $adSources = @('10.0.10.0/24','10.0.20.11','10.0.40.12','10.0.10.254')
    foreach ($port in @('53','88','135','389','445','464','636','3268','3269','49152-65535')) {
        Ensure-RsbRule -Name "RSB-AD-TCP-$port" -Direction Inbound -Protocol TCP -LocalPort $port -RemoteAddress $adSources
    }
    foreach ($port in @('53','88','123','464')) {
        Ensure-RsbRule -Name "RSB-AD-UDP-$port" -Direction Inbound -Protocol UDP -LocalPort $port -RemoteAddress $adSources
    }
    Ensure-RsbRule -Name 'RSB-AD-WinRM-5985' -Direction Inbound -Protocol TCP -LocalPort 5985 -RemoteAddress @('10.0.10.254')
    Ensure-RsbRule -Name 'RSB-AD-ICMPv4' -Direction Inbound -Protocol ICMPv4 -RemoteAddress $adSources
}

if ($Role -eq 'Corporate') {
    Ensure-RsbRule -Name 'RSB-WS01-RDP' -Direction Inbound -Protocol TCP -LocalPort 3389 -RemoteAddress @('10.0.10.0/24','10.0.10.254')
    Ensure-RsbRule -Name 'RSB-WS01-WinRM' -Direction Inbound -Protocol TCP -LocalPort 5985 -RemoteAddress @('10.0.10.254')
    Ensure-RsbRule -Name 'RSB-WS01-SMB' -Direction Inbound -Protocol TCP -LocalPort 445 -RemoteAddress @('10.0.10.2','10.0.10.254')
    Ensure-RsbRule -Name 'RSB-WS01-to-HMI' -Direction Outbound -Protocol TCP -RemotePort 1880 -RemoteAddress @('10.0.20.20')
    Ensure-RsbRule -Name 'RSB-WS01-to-FUXA' -Direction Outbound -Protocol TCP -RemotePort 1881 -RemoteAddress @('10.0.40.10')
    Ensure-RsbRule -Name 'RSB-WS01-to-ScadaLTS' -Direction Outbound -Protocol TCP -RemotePort 8080 -RemoteAddress @('10.0.40.20')
}

if ($Role -eq 'Jump') {
    Ensure-RsbRule -Name 'RSB-JUMP-RDP' -Direction Inbound -Protocol TCP -LocalPort 3389 -RemoteAddress @('10.0.10.0/24','10.0.10.254')
    Ensure-RsbRule -Name 'RSB-JUMP-WinRM' -Direction Inbound -Protocol TCP -LocalPort 5985 -RemoteAddress @('10.0.10.254')
    Ensure-RsbRule -Name 'RSB-JUMP-SMB' -Direction Inbound -Protocol TCP -LocalPort 445 -RemoteAddress @('10.0.10.2','10.0.10.254')
    Ensure-RsbRule -Name 'RSB-JUMP-to-Engineering-RDP' -Direction Outbound -Protocol TCP -RemotePort 3389 -RemoteAddress @('10.0.40.12')
}

if ($Role -eq 'Engineering') {
    Ensure-RsbRule -Name 'RSB-ENG-RDP' -Direction Inbound -Protocol TCP -LocalPort 3389 -RemoteAddress @('10.0.20.11','10.0.10.254')
    Ensure-RsbRule -Name 'RSB-ENG-WinRM' -Direction Inbound -Protocol TCP -LocalPort 5985 -RemoteAddress @('10.0.10.254')
    Ensure-RsbRule -Name 'RSB-ENG-SMB' -Direction Inbound -Protocol TCP -LocalPort 445 -RemoteAddress @('10.0.10.2','10.0.10.254')
    Ensure-RsbRule -Name 'RSB-ENG-to-PLC-Modbus' -Direction Outbound -Protocol TCP -RemotePort 502 -RemoteAddress @('10.0.50.0/24')
    Ensure-RsbRule -Name 'RSB-ENG-to-PLC-Web' -Direction Outbound -Protocol TCP -RemotePort 8080 -RemoteAddress @('10.0.50.0/24')
    Ensure-RsbRule -Name 'RSB-ENG-to-DNP3' -Direction Outbound -Protocol TCP -RemotePort 20000 -RemoteAddress @('10.0.50.116')
    Ensure-RsbRule -Name 'RSB-ENG-to-BACnet' -Direction Outbound -Protocol UDP -RemotePort 47808 -RemoteAddress @('10.0.50.114')
}

[pscustomobject]@{
    Computer = $env:COMPUTERNAME
    Role = $Role
    FirewallProfiles = Get-NetFirewallProfile | Select-Object Name,Enabled,DefaultInboundAction,DefaultOutboundAction
    RulesStagedThisRun = $staged
    Note = 'Firewall profiles were not enabled or disabled by this script.'
} | ConvertTo-Json -Depth 6
