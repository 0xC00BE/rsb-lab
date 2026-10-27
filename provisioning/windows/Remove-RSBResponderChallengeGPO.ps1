[CmdletBinding(SupportsShouldProcess, ConfirmImpact = 'High')]
param(
    [string]$WorkstationName = 'RSB-WS01',
    [string]$ChallengeOuName = 'Responder Challenge',
    [string]$GpoName = 'RSB - WS01 Responder Challenge'
)

$ErrorActionPreference = 'Stop'
Import-Module ActiveDirectory
Import-Module GroupPolicy

$domain = Get-ADDomain
$parentOu = "OU=Workstations,OU=Corporate,OU=RSB,$($domain.DistinguishedName)"
$challengeOu = "OU=$ChallengeOuName,$parentOu"
$computer = Get-ADComputer -Identity $WorkstationName -Properties DistinguishedName

if ($computer.DistinguishedName -like "*,$challengeOu" -and
    $PSCmdlet.ShouldProcess($computer.DistinguishedName, "Move $WorkstationName back to $parentOu")) {
    Move-ADObject -Identity $computer.DistinguishedName -TargetPath $parentOu
}

if (Get-GPO -Name $GpoName -ErrorAction SilentlyContinue) {
    if ($PSCmdlet.ShouldProcess($GpoName, 'Remove challenge GPO')) {
        Remove-GPO -Name $GpoName
    }
}

$ou = Get-ADOrganizationalUnit -Identity $challengeOu -ErrorAction SilentlyContinue
if ($ou) {
    $children = @(Get-ADObject -SearchBase $challengeOu -SearchScope OneLevel -Filter *)
    if ($children.Count -eq 0 -and $PSCmdlet.ShouldProcess($challengeOu, 'Remove empty challenge OU')) {
        Set-ADOrganizationalUnit -Identity $challengeOu -ProtectedFromAccidentalDeletion $false
        Remove-ADOrganizationalUnit -Identity $challengeOu -Confirm:$false
    }
}

[pscustomobject]@{
    WorkstationDn = (Get-ADComputer -Identity $WorkstationName).DistinguishedName
    GpoPresent = [bool](Get-GPO -Name $GpoName -ErrorAction SilentlyContinue)
    ChallengeOuPresent = [bool](Get-ADOrganizationalUnit -Identity $challengeOu -ErrorAction SilentlyContinue)
} | Format-List
