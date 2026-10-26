[CmdletBinding()]
param(
    [string]$ServiceName = 'RSBInventorySync',
    [string]$ServiceAccountName = 'svc_inventory'
)

$ErrorActionPreference = 'Stop'
$dnsPolicy = 'HKLM:\Software\Policies\Microsoft\Windows NT\DNSClient'
$service = Get-CimInstance Win32_Service -Filter "Name='$ServiceName'"
$account = Get-LocalUser -Name $ServiceAccountName -ErrorAction SilentlyContinue
$remoteManagementGroup = Get-LocalGroup -SID 'S-1-5-32-580'

[pscustomobject]@{
    Computer = $env:COMPUTERNAME
    ServiceInstalled = [bool]$service
    ServiceState = $service.State
    ServiceStartMode = $service.StartMode
    ServiceStartName = $service.StartName
    AccountExists = [bool]$account
    AccountEnabled = $account.Enabled
    AccountSid = $account.SID.Value
    RemoteManagementUser = [bool](Get-LocalGroupMember -Group $remoteManagementGroup.Name -ErrorAction SilentlyContinue |
        Where-Object Name -eq "$env:COMPUTERNAME\$ServiceAccountName")
    LlmnrEnabled = (Get-ItemPropertyValue -LiteralPath $dnsPolicy -Name EnableMulticast -ErrorAction SilentlyContinue) -eq 1
    Netbios = @(Get-CimInstance Win32_NetworkAdapterConfiguration -Filter 'IPEnabled=TRUE' |
        Select-Object Index, Description, TcpipNetbiosOptions)
    WinRmListening = [bool](Get-NetTCPConnection -LocalPort 5985 -State Listen -ErrorAction SilentlyContinue)
    ChallengeFirewallRule = [bool](Get-NetFirewallRule -Name 'RSB-CHALLENGE-WINRM' -ErrorAction SilentlyContinue)
    RecentServiceLog = @(Get-Content -LiteralPath 'C:\ProgramData\RSB-Lab\ResponderChallenge\inventory-sync.log' `
        -Tail 5 -ErrorAction SilentlyContinue | ForEach-Object { $_.ToString() })
} | ConvertTo-Json -Depth 5
