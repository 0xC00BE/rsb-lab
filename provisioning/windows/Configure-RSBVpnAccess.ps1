#requires -RunAsAdministrator
[CmdletBinding()]
param([Parameter(Mandatory)][ValidateSet('AD','Corporate','Jump','Engineering')][string]$Role)
$ErrorActionPreference='Stop'
$expected=@{AD='RSBAD01';Corporate='RSB-WS01';Jump='RSB-WS03';Engineering='RSB-WS02'}
if($env:COMPUTERNAME -ne $expected[$Role]){throw 'The selected VPN role does not match this computer.'}
if((Get-CimInstance Win32_ComputerSystem).Domain -ne 'rs.brew'){throw 'This adapter requires the dedicated rs.brew lab domain.'}
$group='RSB VPN Administration';$source='10.254.10.0/24'
# Keep management limited to the administrator tunnel, separate from Corporate.
Enable-PSRemoting -Force -SkipNetworkProfileCheck
Get-NetFirewallRule -DisplayGroup 'Windows Remote Management' -ErrorAction SilentlyContinue | Disable-NetFirewallRule
Set-ItemProperty 'HKLM:\SYSTEM\CurrentControlSet\Control\Terminal Server' -Name fDenyTSConnections -Value 0
Set-ItemProperty 'HKLM:\SYSTEM\CurrentControlSet\Control\Terminal Server\WinStations\RDP-Tcp' -Name UserAuthentication -Value 1
Set-ItemProperty 'HKLM:\SYSTEM\CurrentControlSet\Control\Terminal Server\WinStations\RDP-Tcp' -Name SecurityLayer -Value 2
Get-NetFirewallRule -DisplayGroup 'Remote Desktop' -ErrorAction SilentlyContinue | Disable-NetFirewallRule
Set-Service TermService -StartupType Automatic;Start-Service TermService
$ports=@{TCP=@('445','3389','5985');UDP=@()}
if($Role -eq 'AD'){
 $ports.TCP+=@('53','88','135','389','464','636','3268','3269','49152-65535')
 $ports.UDP=@('53','88','123','389','464')
}
foreach($protocol in @('TCP','UDP')){foreach($port in $ports[$protocol]){
 $name="RSB-VPN-ADMIN-$Role-$protocol-$port"
 $existing=Get-NetFirewallRule -Name $name -ErrorAction SilentlyContinue
 if($existing){
  if($existing.Group -ne $group){throw "Existing rule is outside this adapter: $name"}
  $existing | Get-NetFirewallAddressFilter | Set-NetFirewallAddressFilter -RemoteAddress $source
  $existing | Set-NetFirewallRule -Enabled True -Action Allow -Profile Any
 }else{
  New-NetFirewallRule -Name $name -DisplayName $name -Group $group -Direction Inbound -Action Allow -Profile Any -Enabled True -Protocol $protocol -LocalPort $port -RemoteAddress $source | Out-Null
 }
}}
Set-NetFirewallProfile -Profile Domain,Private,Public -Enabled True
Write-Host "Administrator VPN management enabled for $Role from $source."
