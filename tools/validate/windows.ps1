[CmdletBinding()]
param(
 [Parameter(Mandatory)][ValidateSet('AD','Corporate','Jump','Engineering')][string]$Role,
 [ValidateRange(0,600)][int]$WaitSeconds=180,
 [switch]$RequireVpnManagement
)
$ErrorActionPreference='Stop'
$expected=@{AD='RSBAD01';Corporate='RSB-WS01';Jump='RSB-WS03';Engineering='RSB-WS02'}
if($env:COMPUTERNAME -ne $expected[$Role]){throw 'Role does not match this computer'}
if((Get-CimInstance Win32_ComputerSystem).Domain -ne 'rs.brew'){throw 'Unexpected domain'}
$required=@{AD=@('NTDS','DNS');Corporate=@('RSBInventorySync');Jump=@('RSBEngineeringAgent');Engineering=@()}[$Role]
$deadline=(Get-Date).AddSeconds($WaitSeconds)
do{
 $pending=@($required | Where-Object {(Get-Service -Name $_ -ErrorAction Stop).Status -ne 'Running'})
 if(-not $pending.Count){break}
 if((Get-Date) -ge $deadline){throw ('Services not ready: '+($pending -join ', '))}
 # Windows delayed automatic startup normally waits about two minutes.
 Start-Sleep -Seconds 5
}while($true)
if($Role -ne 'AD' -and -not(Test-ComputerSecureChannel)){throw 'Domain secure channel failed'}
if(@(Get-NetFirewallProfile | Where-Object {-not $_.Enabled}).Count){throw 'A Windows firewall profile is disabled'}
if($RequireVpnManagement -or $Role -in @('Jump','Engineering')){
 if((Get-ItemPropertyValue 'HKLM:\SYSTEM\CurrentControlSet\Control\Terminal Server' fDenyTSConnections) -ne 0){throw 'RDP is disabled'}
 if(-not(Get-NetTCPConnection -State Listen -LocalPort 3389 -ErrorAction SilentlyContinue)){throw 'RDP is not listening'}
}
if($RequireVpnManagement){
 $rules=@(Get-NetFirewallRule -Group 'RSB VPN Administration' -Enabled True)
 if(-not $rules.Count){throw 'Optional administrator VPN host rules are absent'}
 foreach($rule in $rules){
  $addresses=@(($rule | Get-NetFirewallAddressFilter).RemoteAddress)
  # NetSecurity returns CIDR on some builds and an equivalent dotted mask on others.
  if($addresses.Count -ne 1 -or $addresses[0] -notin @('10.254.10.0/24','10.254.10.0/255.255.255.0')){throw 'Unexpected administrator VPN rule scope'}
 }
}
[pscustomobject]@{Computer=$env:COMPUTERNAME;Role=$Role;Domain='rs.brew';ServicesReady=$true;FirewallProfilesEnabled=$true;VpnHostRulesChecked=[bool]$RequireVpnManagement} | ConvertTo-Json -Compress
