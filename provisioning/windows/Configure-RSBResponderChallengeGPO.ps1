[CmdletBinding(SupportsShouldProcess)]
param(
    [string]$WorkstationName = 'RSB-WS01',
    [string]$ChallengeOuName = 'Responder Challenge',
    [string]$GpoName = 'RSB - WS01 Responder Challenge',
    [string]$BackupRoot = 'C:\RSB-Lab\GPO-Backups'
)

$ErrorActionPreference = 'Stop'
Import-Module ActiveDirectory
Import-Module GroupPolicy

function Ensure-Ou {
    param([string]$Name, [string]$Path)

    $dn = "OU=$Name,$Path"
    # Identity lookup throws when the fresh-build OU does not yet exist.
    $escapedName = $Name.Replace('\','\5c').Replace('*','\2a').Replace('(','\28').Replace(')','\29')
    $existing = Get-ADOrganizationalUnit -LDAPFilter "(ou=$escapedName)" `
        -SearchBase $Path -SearchScope OneLevel -ErrorAction Stop
    if ($existing) { return $existing }

    if ($PSCmdlet.ShouldProcess($dn, 'Create challenge OU')) {
        return New-ADOrganizationalUnit -Name $Name -Path $Path -ProtectedFromAccidentalDeletion $true -PassThru
    }
}

$domain = Get-ADDomain
$corporateWorkstations = "OU=Workstations,OU=Corporate,OU=RSB,$($domain.DistinguishedName)"
if (-not (Get-ADOrganizationalUnit -Identity $corporateWorkstations -ErrorAction SilentlyContinue)) {
    throw "Expected parent OU does not exist: $corporateWorkstations"
}

$computer = Get-ADComputer -Identity $WorkstationName -Properties DistinguishedName, Enabled, OperatingSystem
if (-not $computer.Enabled) {
    throw "$WorkstationName is disabled. Enable and validate it before deploying the challenge."
}

$challengeOu = Ensure-Ou -Name $ChallengeOuName -Path $corporateWorkstations
$challengeDn = if ($challengeOu) { $challengeOu.DistinguishedName } else { "OU=$ChallengeOuName,$corporateWorkstations" }

if ($computer.DistinguishedName -notlike "*,$challengeDn") {
    if ($PSCmdlet.ShouldProcess($computer.DistinguishedName, "Move $WorkstationName to $challengeDn")) {
        Move-ADObject -Identity $computer.DistinguishedName -TargetPath $challengeDn
    }
}

$gpo = Get-GPO -Name $GpoName -ErrorAction SilentlyContinue
if (-not $gpo -and $PSCmdlet.ShouldProcess($GpoName, 'Create challenge GPO')) {
    $gpo = New-GPO -Name $GpoName -Comment 'Intentionally enables LLMNR only for the isolated RSB-WS01 Responder exercise.'
}

if ($gpo) {
    $existingLink = (Get-GPInheritance -Target $challengeDn).GpoLinks |
        Where-Object DisplayName -eq $GpoName
    if (-not $existingLink -and $PSCmdlet.ShouldProcess($challengeDn, "Link $GpoName")) {
        New-GPLink -Name $GpoName -Target $challengeDn -LinkEnabled Yes -Order 1 | Out-Null
    }

    # The parent RSB audit GPO disables LLMNR. A child-OU policy with value 1
    # intentionally overrides it for this one exercise workstation.
    if ($PSCmdlet.ShouldProcess($GpoName, 'Enable LLMNR for the challenge OU')) {
        Set-GPRegistryValue -Name $GpoName `
            -Key 'HKLM\Software\Policies\Microsoft\Windows NT\DNSClient' `
            -ValueName 'EnableMulticast' -Type DWord -Value 1 | Out-Null
    }

    New-Item -ItemType Directory -Path $BackupRoot -Force | Out-Null
    $stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
    $backupPath = Join-Path $BackupRoot $stamp
    New-Item -ItemType Directory -Path $backupPath -Force | Out-Null
    Backup-GPO -Guid $gpo.Id -Path $backupPath -Comment 'Before/after snapshot for the RSB Responder challenge' | Out-Null
}

$resultComputer = Get-ADComputer -Identity $WorkstationName -Properties DistinguishedName, Enabled, OperatingSystem
$resultGpo = Get-GPO -Name $GpoName -ErrorAction SilentlyContinue
[pscustomobject]@{
    Workstation       = $resultComputer.Name
    OperatingSystem   = $resultComputer.OperatingSystem
    ComputerEnabled   = $resultComputer.Enabled
    DistinguishedName = $resultComputer.DistinguishedName
    ChallengeOu       = $challengeDn
    GpoName           = $resultGpo.DisplayName
    GpoId             = $resultGpo.Id
    LlmnrPolicy       = (Get-GPRegistryValue -Name $GpoName `
        -Key 'HKLM\Software\Policies\Microsoft\Windows NT\DNSClient' `
        -ValueName 'EnableMulticast' -ErrorAction SilentlyContinue).Value
    NextStep          = 'Run Install-RSBResponderChallenge.ps1 locally as Administrator on RSB-WS01, then reboot or run gpupdate /force.'
} | Format-List
