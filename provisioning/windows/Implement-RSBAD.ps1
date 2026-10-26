$ErrorActionPreference = 'Stop'
Import-Module ActiveDirectory
Import-Module GroupPolicy
Import-Module DnsServer

$domain = Get-ADDomain
$domainDN = $domain.DistinguishedName
$domainNetBIOS = $domain.NetBIOSName
$changeLog = [System.Collections.Generic.List[string]]::new()

function Add-Change([string]$Message) {
    $changeLog.Add($Message)
}

function Ensure-OU {
    param([string]$Name, [string]$Path)
    $dn = "OU=$Name,$Path"
    $existing = Get-ADOrganizationalUnit -LDAPFilter "(ou=$Name)" -SearchBase $Path `
        -SearchScope OneLevel -ErrorAction SilentlyContinue
    if (-not $existing) {
        New-ADOrganizationalUnit -Name $Name -Path $Path -ProtectedFromAccidentalDeletion $true
        Add-Change "Created OU $dn"
    }
    return $dn
}

function Ensure-Group {
    param([string]$Name, [string]$Description, [string]$Path)
    $group = Get-ADGroup -Filter "SamAccountName -eq '$Name'" -ErrorAction SilentlyContinue
    if (-not $group) {
        $group = New-ADGroup -Name $Name -SamAccountName $Name -GroupCategory Security `
            -GroupScope Global -Path $Path -Description $Description -PassThru
        Add-Change "Created group $Name"
    } else {
        Set-ADGroup -Identity $group -Description $Description
    }
    return $group
}

function Ensure-User {
    param(
        [string]$Sam,
        [string]$GivenName,
        [string]$Surname,
        [string]$DisplayName,
        [string]$Password,
        [string]$Description,
        [string]$Department,
        [string]$Path,
        [bool]$Enabled = $true
    )
    $securePassword = ConvertTo-SecureString $Password -AsPlainText -Force
    $user = Get-ADUser -Filter "SamAccountName -eq '$Sam'" -ErrorAction SilentlyContinue
    if (-not $user) {
        $user = New-ADUser -Name $DisplayName -GivenName $GivenName -Surname $Surname `
            -DisplayName $DisplayName -SamAccountName $Sam -UserPrincipalName "$Sam@$($domain.DNSRoot)" `
            -AccountPassword $securePassword -Enabled $Enabled -ChangePasswordAtLogon $false `
            -PasswordNeverExpires $true -Description $Description -Department $Department `
            -Path $Path -PassThru
        Add-Change "Created user $Sam (Enabled=$Enabled)"
    } else {
        Set-ADUser -Identity $user -DisplayName $DisplayName -Description $Description `
            -Department $Department -PasswordNeverExpires $true
        Set-ADAccountPassword -Identity $user -Reset -NewPassword $securePassword
        if ($Enabled) { Enable-ADAccount -Identity $user } else { Disable-ADAccount -Identity $user }
        Add-Change "Updated existing user $Sam (Enabled=$Enabled)"
    }
    return $user
}

function Ensure-Member {
    param([string]$Group, [string]$Member)
    $present = Get-ADGroupMember -Identity $Group -Recursive:$false -ErrorAction Stop |
        Where-Object { $_.SamAccountName -eq $Member -or $_.Name -eq $Member }
    if (-not $present) {
        Add-ADGroupMember -Identity $Group -Members $Member
        Add-Change "Added $Member to $Group"
    }
}

function Ensure-GPO {
    param([string]$Name, [string]$Target)
    $gpo = Get-GPO -Name $Name -ErrorAction SilentlyContinue
    if (-not $gpo) {
        $gpo = New-GPO -Name $Name
        Add-Change "Created GPO $Name"
    }
    $link = (Get-GPInheritance -Target $Target).GpoLinks | Where-Object DisplayName -eq $Name
    if (-not $link) {
        New-GPLink -Name $Name -Target $Target -LinkEnabled Yes | Out-Null
        Add-Change "Linked GPO $Name to $Target"
    }
    return $gpo
}

# Organizational structure
$ouRoot = Ensure-OU -Name 'RSB' -Path $domainDN
$ouGroups = Ensure-OU -Name 'Groups' -Path $ouRoot
$ouCorporate = Ensure-OU -Name 'Corporate' -Path $ouRoot
$ouCorporateUsers = Ensure-OU -Name 'Users' -Path $ouCorporate
$ouCorporateComputers = Ensure-OU -Name 'Workstations' -Path $ouCorporate
$ouOperations = Ensure-OU -Name 'Operations' -Path $ouRoot
$ouOperationsUsers = Ensure-OU -Name 'Users' -Path $ouOperations
$ouDMZ = Ensure-OU -Name 'DMZ' -Path $ouRoot
$ouDMZComputers = Ensure-OU -Name 'Workstations' -Path $ouDMZ
$ouOT = Ensure-OU -Name 'OT' -Path $ouRoot
$ouOTUsers = Ensure-OU -Name 'Users' -Path $ouOT
$ouOTComputers = Ensure-OU -Name 'Workstations' -Path $ouOT
$ouServices = Ensure-OU -Name 'Service Accounts' -Path $ouOT
$ouDisabled = Ensure-OU -Name 'Disabled Objects' -Path $ouRoot

# Security groups, including realistic unused groups.
$groups = @(
    @('RSB-Employees', 'All active RSB employee identities'),
    @('RSB-Corporate-Users', 'Corporate office users'),
    @('RSB-Brewery-Operations', 'Brewery production operations staff'),
    @('RSB-OT-Engineering', 'OT engineering personnel'),
    @('RSB-Maintenance', 'Plant maintenance personnel'),
    @('RSB-Quality-Assurance', 'Quality assurance and laboratory personnel'),
    @('RSB-Logistics', 'Warehouse and logistics personnel'),
    @('RSB-Finance', 'Finance department personnel'),
    @('RSB-HR', 'Human resources personnel'),
    @('RSB-IT-Support', 'IT support personnel'),
    @('RSB-Contractors', 'External contractor identities'),
    @('RSB-BrewExpansion-Project', 'Temporary brewery expansion project team'),
    @('RSB-Jump-RDP', 'Users permitted to use the DMZ jump workstation'),
    @('RSB-Engineering-RDP', 'Users permitted to use the OT engineering workstation'),
    @('RSB-NodeRED-Deployment', 'Node-RED deployment operators'),
    @('RSB-SCADA-Operators', 'SCADA operator identities'),
    @('RSB-Remote-Management', 'Infrastructure remote management identities'),
    @('RSB-Legacy-ERP', 'Legacy ERP access group; currently unused'),
    @('RSB-Backup-Operators', 'Backup application operators; currently unused'),
    @('RSB-BMS-Operators', 'Building management operators; currently unused'),
    @('RSB-Packaging-Integration', 'Packaging integration operators; currently unused')
)
foreach ($entry in $groups) { Ensure-Group -Name $entry[0] -Description $entry[1] -Path $ouGroups | Out-Null }

# Users used by the intended paths.
$users = @(
    @('sara.nilsen','Sara','Nilsen','Sara Nilsen','PublicLab!User01','Brewery expansion project analyst','Corporate',$ouCorporateUsers,$true),
    @('henrik.solberg','Henrik','Solberg','Henrik Solberg','PublicLab!User02','OT controls engineer','OT Engineering',$ouOTUsers,$true),
    @('anna.lund','Anna','Lund','Anna Lund','PublicLab!User03','Service desk analyst','IT',$ouCorporateUsers,$true),
    @('marius.berg','Marius','Berg','Marius Berg','PublicLab!User04','Brewhouse shift supervisor','Operations',$ouOperationsUsers,$true),
    @('ingrid.haugen','Ingrid','Haugen','Ingrid Haugen','PublicLab!User05','Quality assurance specialist','Quality',$ouOperationsUsers,$true),
    @('erik.dahl','Erik','Dahl','Erik Dahl','PublicLab!User06','Maintenance technician','Maintenance',$ouOperationsUsers,$true),
    @('lina.moen','Lina','Moen','Lina Moen','PublicLab!User07','Financial analyst','Finance',$ouCorporateUsers,$true),
    @('thea.johansen','Thea','Johansen','Thea Johansen','PublicLab!User08','Human resources adviser','HR',$ouCorporateUsers,$true),
    @('anders.lie','Anders','Lie','Anders Lie','PublicLab!User09','IT systems technician','IT',$ouCorporateUsers,$true),
    @('sofie.bakke','Sofie','Bakke','Sofie Bakke','PublicLab!User10','Packaging line coordinator','Operations',$ouOperationsUsers,$true),
    @('jonas.sveen','Jonas','Sveen','Jonas Sveen','PublicLab!User11','Warehouse and logistics planner','Logistics',$ouOperationsUsers,$true),
    @('nora.kristiansen','Nora','Kristiansen','Nora Kristiansen','PublicLab!User12','Quality laboratory technician','Quality',$ouOperationsUsers,$true),
    @('martin.iversen','Martin','Iversen','Martin Iversen','PublicLab!User13','Operations director','Management',$ouCorporateUsers,$true),
    @('camilla.aasen','Camilla','Aasen','Camilla Aasen','PublicLab!User14','Procurement specialist','Procurement',$ouCorporateUsers,$true),
    @('victor.nordby','Victor','Nordby','Victor Nordby','PublicLab!User15','Automation contractor','Contractor',$ouCorporateUsers,$true),
    @('kari.holm','Kari','Holm','Kari Holm','PublicLab!User16','Former quality employee','Former Employee',$ouDisabled,$false),
    @('legacy.vendor','Legacy','Vendor','Legacy Vendor','PublicLab!User17','Retired vendor integration identity','Vendor',$ouDisabled,$false)
)
foreach ($u in $users) {
    Ensure-User -Sam $u[0] -GivenName $u[1] -Surname $u[2] -DisplayName $u[3] `
        -Password $u[4] -Description $u[5] -Department $u[6] -Path $u[7] -Enabled $u[8] | Out-Null
}

$serviceUsers = @(
    @('svc.nodered','Node-RED Deployment','PublicLab!App01','Lab-only Node-RED deployment identity'),
    @('svc.scadahist','SCADA Historian','PublicLab!App02','Inactive SCADA historian service identity'),
    @('svc.backup','Backup Service','PublicLab!App03','Inactive backup service identity'),
    @('svc.erp','ERP Integration','PublicLab!App04','Inactive legacy ERP service identity'),
    @('svc.bms','BMS Integration','PublicLab!App05','Inactive building-management service identity'),
    @('svc.packaging','Packaging Integration','PublicLab!App06','Inactive packaging integration service identity')
)
foreach ($u in $serviceUsers) {
    Ensure-User -Sam $u[0] -GivenName 'Service' -Surname $u[1] -DisplayName $u[1] `
        -Password $u[2] -Description $u[3] -Department 'Service Accounts' -Path $ouServices -Enabled $true | Out-Null
}

# Normal memberships.
$memberships = @{
    'RSB-Corporate-Users' = @('sara.nilsen','anna.lund','lina.moen','thea.johansen','anders.lie','martin.iversen','camilla.aasen')
    'RSB-Brewery-Operations' = @('marius.berg','sofie.bakke')
    'RSB-OT-Engineering' = @('henrik.solberg')
    'RSB-Maintenance' = @('erik.dahl')
    'RSB-Quality-Assurance' = @('ingrid.haugen','nora.kristiansen')
    'RSB-Logistics' = @('jonas.sveen')
    'RSB-Finance' = @('lina.moen')
    'RSB-HR' = @('thea.johansen')
    'RSB-IT-Support' = @('anna.lund','anders.lie')
    'RSB-Contractors' = @('victor.nordby')
    'RSB-BrewExpansion-Project' = @('sara.nilsen','victor.nordby')
    'RSB-Engineering-RDP' = @('henrik.solberg')
    'RSB-NodeRED-Deployment' = @('svc.nodered')
    'RSB-SCADA-Operators' = @('henrik.solberg','marius.berg')
    'RSB-Packaging-Integration' = @('svc.packaging')
}
foreach ($groupName in $memberships.Keys) {
    foreach ($member in $memberships[$groupName]) { Ensure-Member -Group $groupName -Member $member }
}
foreach ($employee in @('sara.nilsen','anna.lund','marius.berg','ingrid.haugen','erik.dahl','lina.moen','thea.johansen','anders.lie','sofie.bakke','jonas.sveen','nora.kristiansen','martin.iversen','camilla.aasen')) {
    Ensure-Member -Group 'RSB-Employees' -Member $employee
}

# Deliberate Path 2 weakness: project membership unintentionally grants jump-host RDP.
Ensure-Member -Group 'RSB-Jump-RDP' -Member 'RSB-BrewExpansion-Project'

# Reorganize the known computer objects. RSB-WS02 is the intended 10.0.40.12
# engineering workstation; its stale disabled computer account is re-enabled.
$computerMoves = @{
    'RSB-WS01' = $ouCorporateComputers
    'RSB-WS03' = $ouDMZComputers
    'RSB-WS02' = $ouOTComputers
}
foreach ($name in $computerMoves.Keys) {
    $computer = Get-ADComputer -Identity $name -ErrorAction SilentlyContinue
    if ($computer) {
        if ($name -eq 'RSB-WS02' -and -not $computer.Enabled) {
            Enable-ADAccount -Identity $computer
            Add-Change 'Re-enabled computer account RSB-WS02 for the OT engineering workstation'
        }
        if ($computer.DistinguishedName -notlike "*,$($computerMoves[$name])") {
            Move-ADObject -Identity $computer -TargetPath $computerMoves[$name]
            Add-Change "Moved $name to $($computerMoves[$name])"
        }
    }
}

# Restore an explicit DNS record for the engineering workstation.
$dnsRecord = Get-DnsServerResourceRecord -ZoneName $domain.DNSRoot -Name 'RSB-WS02' -RRType A -ErrorAction SilentlyContinue
if (-not $dnsRecord) {
    Add-DnsServerResourceRecordA -ZoneName $domain.DNSRoot -Name 'RSB-WS02' -IPv4Address '10.0.40.12' -TimeToLive 01:00:00
    Add-Change 'Added DNS A record RSB-WS02.rs.brew -> 10.0.40.12'
}

# Security/audit policy GPO. Firewall profile state is intentionally not set;
# the owner will reactivate Windows Firewall after validation.
$auditGpo = Ensure-GPO -Name 'RSB - Audit and PowerShell Logging' -Target $ouRoot
$auditSettings = @(
    @('HKLM\Software\Policies\Microsoft\Windows\PowerShell\ScriptBlockLogging','EnableScriptBlockLogging','DWord',1),
    @('HKLM\Software\Policies\Microsoft\Windows\PowerShell\ModuleLogging','EnableModuleLogging','DWord',1),
    @('HKLM\Software\Policies\Microsoft\Windows\PowerShell\ModuleLogging\ModuleNames','*','String','*'),
    @('HKLM\Software\Policies\Microsoft\Windows\PowerShell\Transcription','EnableTranscripting','DWord',1),
    @('HKLM\Software\Policies\Microsoft\Windows\PowerShell\Transcription','EnableInvocationHeader','DWord',1),
    @('HKLM\Software\Policies\Microsoft\Windows\PowerShell\Transcription','OutputDirectory','String','C:\ProgramData\RSB\Transcripts'),
    @('HKLM\Software\Microsoft\Windows\CurrentVersion\Policies\System\Audit','ProcessCreationIncludeCmdLine_Enabled','DWord',1),
    @('HKLM\Software\Policies\Microsoft\Windows\EventLog\Security','MaxSize','DWord',268435456),
    @('HKLM\Software\Policies\Microsoft\Windows NT\DNSClient','EnableMulticast','DWord',0),
    @('HKLM\SYSTEM\CurrentControlSet\Control\SecurityProviders\WDigest','UseLogonCredential','DWord',0)
)
foreach ($setting in $auditSettings) {
    Set-GPRegistryValue -Name $auditGpo.DisplayName -Key $setting[0] -ValueName $setting[1] `
        -Type $setting[2] -Value $setting[3] | Out-Null
}

$jumpGpo = Ensure-GPO -Name 'RSB - DMZ Jump Workstation' -Target $ouDMZComputers
$engineeringGpo = Ensure-GPO -Name 'RSB - OT Engineering Workstation' -Target $ouOTComputers
foreach ($gpoName in @($jumpGpo.DisplayName, $engineeringGpo.DisplayName)) {
    Set-GPRegistryValue -Name $gpoName `
        -Key 'HKLM\Software\Policies\Microsoft\Windows NT\Terminal Services' `
        -ValueName 'fDenyTSConnections' -Type DWord -Value 0 | Out-Null
    Set-GPRegistryValue -Name $gpoName `
        -Key 'HKLM\SYSTEM\CurrentControlSet\Control\Terminal Server\WinStations\RDP-Tcp' `
        -ValueName 'UserAuthentication' -Type DWord -Value 1 | Out-Null
    Set-GPRegistryValue -Name $gpoName `
        -Key 'HKLM\SYSTEM\CurrentControlSet\Control\Terminal Server\WinStations\RDP-Tcp' `
        -ValueName 'SecurityLayer' -Type DWord -Value 2 | Out-Null
    Set-GPRegistryValue -Name $gpoName `
        -Key 'HKLM\SYSTEM\CurrentControlSet\Control\Terminal Server\WinStations\RDP-Tcp' `
        -ValueName 'MinEncryptionLevel' -Type DWord -Value 3 | Out-Null
}

# Deliberate Path 1 weakness: an over-readable deployment share exposes only
# the lab Node-RED credential, never a Windows administrator credential.
$shareRoot = 'C:\RSB-Lab\EngineeringDeploy'
New-Item -ItemType Directory -Path $shareRoot -Force | Out-Null
$deploymentNote = @'
RSB Node-RED deployment endpoint
URL: http://10.0.20.20:1880/
Username: svc.nodered
Password: PublicLab!App01

Legacy note: retained for the brewery expansion project deployment team.
'@
Set-Content -LiteralPath (Join-Path $shareRoot 'nodered-deployment.txt') -Value $deploymentNote -Encoding UTF8
& icacls.exe $shareRoot /inheritance:r /grant:r `
    "$domainNetBIOS\Domain Admins:(OI)(CI)(F)" `
    'SYSTEM:(OI)(CI)(F)' `
    "$domainNetBIOS\RSB-BrewExpansion-Project:(OI)(CI)(RX)" | Out-Null
$share = Get-SmbShare -Name 'EngineeringDeploy$' -ErrorAction SilentlyContinue
if (-not $share) {
    New-SmbShare -Name 'EngineeringDeploy$' -Path $shareRoot `
        -FullAccess "$domainNetBIOS\Domain Admins", 'SYSTEM' `
        -ReadAccess "$domainNetBIOS\RSB-BrewExpansion-Project" `
        -FolderEnumerationMode AccessBased | Out-Null
    Add-Change 'Created hidden SMB share EngineeringDeploy$ for Path 1'
}

[pscustomobject]@{
    Computer = $env:COMPUTERNAME
    Domain = $domain.DNSRoot
    Changes = $changeLog
    UserCount = (Get-ADUser -Filter *).Count
    CustomGroupCount = (Get-ADGroup -Filter "Name -like 'RSB-*'").Count
    GPOs = (Get-GPO -All | Where-Object DisplayName -like 'RSB -*' | Select-Object -ExpandProperty DisplayName)
} | ConvertTo-Json -Depth 5
