#requires -RunAsAdministrator
[CmdletBinding()]
param([securestring]$SafeModeAdministratorPassword)
$ErrorActionPreference = 'Stop'
if ($env:COMPUTERNAME -ne 'RSBAD01') { throw 'Rename this fresh server RSBAD01 and reboot first.' }
if (-not $SafeModeAdministratorPassword) {
    $SafeModeAdministratorPassword = Read-Host 'Choose a private DSRM password' -AsSecureString
}
Install-WindowsFeature AD-Domain-Services -IncludeManagementTools | Out-Null
Import-Module ADDSDeployment
Install-ADDSForest -DomainName 'rs.brew' -DomainNetbiosName 'RS' -InstallDNS `
    -SafeModeAdministratorPassword $SafeModeAdministratorPassword -Force
