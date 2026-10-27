$ErrorActionPreference = 'Stop'
Import-Module ActiveDirectory
Import-Module GroupPolicy
Import-Module DnsServer

$expectedUsers = @(
    'sara.nilsen','henrik.solberg','svc.nodered','anna.lund','marius.berg',
    'ingrid.haugen','erik.dahl','lina.moen','thea.johansen','anders.lie',
    'sofie.bakke','jonas.sveen','nora.kristiansen','martin.iversen',
    'camilla.aasen','victor.nordby','svc.scadahist','svc.backup','svc.erp',
    'svc.bms','svc.packaging','kari.holm','legacy.vendor'
)
$expectedGroups = @(
    'RSB-Employees','RSB-Corporate-Users','RSB-Brewery-Operations',
    'RSB-OT-Engineering','RSB-Maintenance','RSB-Quality-Assurance',
    'RSB-Logistics','RSB-Finance','RSB-HR','RSB-IT-Support','RSB-Contractors',
    'RSB-BrewExpansion-Project','RSB-Jump-RDP','RSB-Engineering-RDP',
    'RSB-NodeRED-Deployment','RSB-SCADA-Operators','RSB-Remote-Management',
    'RSB-Legacy-ERP','RSB-Backup-Operators','RSB-BMS-Operators',
    'RSB-Packaging-Integration'
)

$missingUsers = @($expectedUsers | Where-Object { -not (Get-ADUser -Identity $_ -ErrorAction SilentlyContinue) })
$missingGroups = @($expectedGroups | Where-Object { -not (Get-ADGroup -Identity $_ -ErrorAction SilentlyContinue) })
$jumpMembers = @(Get-ADGroupMember -Identity 'RSB-Jump-RDP' | Select-Object Name,SamAccountName,ObjectClass)
$engineeringMembers = @(Get-ADGroupMember -Identity 'RSB-Engineering-RDP' | Select-Object Name,SamAccountName,ObjectClass)
$share = Get-SmbShare -Name 'EngineeringDeploy$' -ErrorAction SilentlyContinue
$shareAccess = if ($share) { @(Get-SmbShareAccess -Name 'EngineeringDeploy$' | Select-Object AccountName,AccessControlType,AccessRight) } else { @() }
$dns = Get-DnsServerResourceRecord -ZoneName 'rs.brew' -Name 'RSB-WS02' -RRType A -ErrorAction SilentlyContinue
$computers = @('RSB-WS01','RSB-WS02','RSB-WS03') | ForEach-Object {
    Get-ADComputer -Identity $_ -Properties Enabled,DNSHostName |
        Select-Object Name,Enabled,DNSHostName,DistinguishedName
}
$gpos = Get-GPO -All | Where-Object DisplayName -Like 'RSB -*' |
    Select-Object DisplayName,Id,GpoStatus,ModificationTime

[pscustomobject]@{
    Passed = ($missingUsers.Count -eq 0 -and $missingGroups.Count -eq 0 -and $null -ne $share -and $null -ne $dns)
    MissingUsers = $missingUsers
    MissingGroups = $missingGroups
    TotalDomainUsers = (Get-ADUser -Filter *).Count
    CustomGroups = (Get-ADGroup -Filter "Name -like 'RSB-*'").Count
    JumpGroupDirectMembers = $jumpMembers
    EngineeringGroupDirectMembers = $engineeringMembers
    SharePath = $share.Path
    ShareAccess = $shareAccess
    EngineeringDnsAddress = $dns.RecordData.IPv4Address.IPAddressToString
    Computers = $computers
    GPOs = $gpos
} | ConvertTo-Json -Depth 7
