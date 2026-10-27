[CmdletBinding(SupportsShouldProcess)]
param(
    [string]$ExpectedComputerName = 'RSB-WS01',
    [string]$ServiceName = 'RSBInventorySync',
    [string]$ServiceAccountName = 'svc_inventory',
    [securestring]$ServiceAccountPassword,
    [string]$MissingHost = 'RSB-FILE-OLD',
    [string]$MissingShare = 'Inventory$',
    [ValidateRange(30, 3600)]
    [int]$IntervalSeconds = 120,
    [string[]]$WinRmRemoteAddress = @('10.0.10.0/24', '10.0.10.254'),
    [switch]$ForceComputerName
)

$ErrorActionPreference = 'Stop'
$installRoot = 'C:\ProgramData\RSB-Lab\ResponderChallenge'
$binaryPath = Join-Path $installRoot 'RSBInventorySync.exe'
$baselinePath = Join-Path $installRoot 'baseline.json'
$logPath = Join-Path $installRoot 'inventory-sync.log'

if ($PSVersionTable.PSEdition -ne 'Desktop') {
    throw 'Run this installer with Windows PowerShell 5.1 (powershell.exe). Its Add-Type compiler builds the .NET Framework Windows-service executable.'
}

if (-not $ForceComputerName -and $env:COMPUTERNAME -ne $ExpectedComputerName) {
    throw "This script is intended for $ExpectedComputerName, but it is running on $env:COMPUTERNAME. Use -ForceComputerName only for an intentional clone."
}
if (-not $MissingHost -or $MissingHost -notmatch '^[A-Za-z0-9-]{1,63}$') {
    throw 'MissingHost must be a single-label hostname containing only letters, digits, and hyphens.'
}
if (-not $MissingShare -or $MissingShare -notmatch '^[A-Za-z0-9_$-]{1,80}$') {
    throw 'MissingShare contains unsupported characters.'
}
if (-not $ServiceAccountPassword) {
    $ServiceAccountPassword = Read-Host "Enter the lab-only password for .\$ServiceAccountName" -AsSecureString
}

$admin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole(
    [Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $admin) { throw 'Run this script from an elevated Windows PowerShell session.' }

New-Item -ItemType Directory -Path $installRoot -Force | Out-Null

$ipAdapters = @(Get-CimInstance Win32_NetworkAdapterConfiguration -Filter 'IPEnabled=TRUE')
if (-not (Test-Path -LiteralPath $baselinePath)) {
    $llmnr = Get-ItemPropertyValue `
        -LiteralPath 'HKLM:\Software\Policies\Microsoft\Windows NT\DNSClient' `
        -Name EnableMulticast -ErrorAction SilentlyContinue
    [pscustomobject]@{
        CapturedAt = (Get-Date).ToString('o')
        Computer = $env:COMPUTERNAME
        LlmnrEnableMulticast = $llmnr
        Netbios = @($ipAdapters | Select-Object Index, Description, TcpipNetbiosOptions)
        WinRmStartType = (Get-CimInstance Win32_Service -Filter "Name='WinRM'").StartMode
        WinRmState = (Get-CimInstance Win32_Service -Filter "Name='WinRM'").State
        WinRmFirewallRules = @(Get-NetFirewallRule -DisplayGroup 'Windows Remote Management' -ErrorAction SilentlyContinue |
            Select-Object Name, Enabled)
        ExistingService = [bool](Get-Service -Name $ServiceName -ErrorAction SilentlyContinue)
        ExistingUser = [bool](Get-LocalUser -Name $ServiceAccountName -ErrorAction SilentlyContinue)
    } | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $baselinePath -Encoding UTF8
}

# Enable LLMNR locally. The companion child-OU GPO preserves this setting
# against the parent audit GPO that disables multicast name resolution.
$dnsPolicy = 'HKLM:\Software\Policies\Microsoft\Windows NT\DNSClient'
New-Item -Path $dnsPolicy -Force | Out-Null
Set-ItemProperty -LiteralPath $dnsPolicy -Name EnableMulticast -Type DWord -Value 1

# Explicitly enable NetBIOS over TCP/IP on each active IP-enabled adapter.
foreach ($adapter in $ipAdapters) {
    $result = Invoke-CimMethod -InputObject $adapter -MethodName SetTcpipNetbios -Arguments @{ TcpipNetbiosOptions = 1 }
    if ($result.ReturnValue -notin 0, 1) {
        throw "Failed to enable NetBIOS on adapter index $($adapter.Index); return value $($result.ReturnValue)."
    }
}

$localUser = Get-LocalUser -Name $ServiceAccountName -ErrorAction SilentlyContinue
if (-not $localUser) {
    New-LocalUser -Name $ServiceAccountName -Password $ServiceAccountPassword `
        -Description 'RSB lab inventory name-resolution exercise' `
        -AccountNeverExpires -PasswordNeverExpires | Out-Null
} else {
    Set-LocalUser -Name $ServiceAccountName -Password $ServiceAccountPassword `
        -Description 'RSB lab inventory name-resolution exercise' `
        -AccountNeverExpires -PasswordNeverExpires $true
}
Enable-LocalUser -Name $ServiceAccountName

$remoteManagementGroup = Get-LocalGroup -SID 'S-1-5-32-580'
if (-not (Get-LocalGroupMember -Group $remoteManagementGroup.Name -ErrorAction SilentlyContinue |
        Where-Object Name -eq "$env:COMPUTERNAME\$ServiceAccountName")) {
    Add-LocalGroupMember -Group $remoteManagementGroup.Name -Member $ServiceAccountName
}

function Grant-LogOnAsService {
    param([string]$AccountSid)

    $cfg = Join-Path $env:TEMP "rsb-secpol-$([guid]::NewGuid().ToString('N')).inf"
    $db = Join-Path $env:TEMP "rsb-secpol-$([guid]::NewGuid().ToString('N')).sdb"
    try {
        & secedit.exe /export /cfg $cfg /areas USER_RIGHTS /quiet | Out-Null
        if ($LASTEXITCODE -ne 0) { throw "secedit export failed with exit code $LASTEXITCODE" }
        $lines = [Collections.Generic.List[string]](Get-Content -LiteralPath $cfg)
        $index = -1
        for ($i = 0; $i -lt $lines.Count; $i++) {
            if ($lines[$i] -match '^SeServiceLogonRight\s*=') { $index = $i; break }
        }
        $sidToken = "*$AccountSid"
        if ($index -ge 0) {
            $current = ($lines[$index] -split '=', 2)[1].Trim()
            $members = @($current -split ',' | Where-Object { $_ })
            if ($members -notcontains $sidToken) { $members += $sidToken }
            $lines[$index] = 'SeServiceLogonRight = ' + ($members -join ',')
        } else {
            $privilegeIndex = $lines.IndexOf('[Privilege Rights]')
            if ($privilegeIndex -lt 0) { throw 'The exported security policy has no [Privilege Rights] section.' }
            $lines.Insert($privilegeIndex + 1, "SeServiceLogonRight = $sidToken")
        }
        Set-Content -LiteralPath $cfg -Value $lines -Encoding Unicode
        & secedit.exe /configure /db $db /cfg $cfg /areas USER_RIGHTS /quiet | Out-Null
        if ($LASTEXITCODE -ne 0) { throw "secedit configure failed with exit code $LASTEXITCODE" }
    } finally {
        Remove-Item -LiteralPath $cfg, $db -Force -ErrorAction SilentlyContinue
    }
}

$localUser = Get-LocalUser -Name $ServiceAccountName
Grant-LogOnAsService -AccountSid $localUser.SID.Value

# Compile a small native Windows service. It only performs a read attempt to
# the deliberately nonexistent UNC path and writes a local diagnostic log.
$serviceSource = @"
using System;
using System.IO;
using System.ServiceProcess;
using System.Threading;

public sealed class RSBInventorySyncService : ServiceBase
{
    private Timer timer;
    private int busy;
    private const string Target = @"\\$MissingHost\$MissingShare";
    private const string LogPath = @"$logPath";

    public RSBInventorySyncService()
    {
        ServiceName = "$ServiceName";
        CanStop = true;
        AutoLog = false;
    }

    protected override void OnStart(string[] args)
    {
        timer = new Timer(CheckInventory, null, TimeSpan.Zero, TimeSpan.FromSeconds($IntervalSeconds));
    }

    private void CheckInventory(object state)
    {
        if (Interlocked.Exchange(ref busy, 1) != 0) return;
        try
        {
            Directory.GetFileSystemEntries(Target, "ws01.json");
            WriteLog("Inventory source responded.");
        }
        catch (Exception ex)
        {
            WriteLog("Inventory sync unavailable: " + ex.GetType().Name);
        }
        finally
        {
            Interlocked.Exchange(ref busy, 0);
        }
    }

    private static void WriteLog(string message)
    {
        try { File.AppendAllText(LogPath, DateTime.UtcNow.ToString("o") + " " + message + Environment.NewLine); }
        catch { }
    }

    protected override void OnStop()
    {
        if (timer != null) timer.Dispose();
    }

    public static void Main()
    {
        ServiceBase.Run(new RSBInventorySyncService());
    }
}
"@

Get-Service -Name $ServiceName -ErrorAction SilentlyContinue | Stop-Service -Force -ErrorAction SilentlyContinue
if (Test-Path -LiteralPath $binaryPath) { Remove-Item -LiteralPath $binaryPath -Force }
Add-Type -TypeDefinition $serviceSource -Language CSharp `
    -ReferencedAssemblies @('System.dll', 'System.ServiceProcess.dll') `
    -OutputAssembly $binaryPath -OutputType WindowsApplication

$passwordPointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($ServiceAccountPassword)
$plainPassword = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($passwordPointer)
try {
    $existingService = Get-CimInstance Win32_Service -Filter "Name='$ServiceName'" -ErrorAction SilentlyContinue
    if ($existingService) {
        $change = Invoke-CimMethod -InputObject $existingService -MethodName Change -Arguments @{
            PathName = "`"$binaryPath`""
            StartMode = 'Automatic'
            StartName = ".\$ServiceAccountName"
            StartPassword = $plainPassword
        }
        if ($change.ReturnValue -ne 0) { throw "Win32_Service.Change failed with return value $($change.ReturnValue)" }
    } else {
        $create = Invoke-CimMethod -ClassName Win32_Service -MethodName Create -Arguments @{
            Name = $ServiceName
            DisplayName = 'RSB Inventory Synchronization'
            PathName = "`"$binaryPath`""
            ServiceType = [byte]16
            ErrorControl = [byte]1
            StartMode = 'Automatic'
            DesktopInteract = $false
            StartName = ".\$ServiceAccountName"
            StartPassword = $plainPassword
        }
        if ($create.ReturnValue -ne 0) { throw "Win32_Service.Create failed with return value $($create.ReturnValue)" }
    }
} finally {
    $plainPassword = $null
    [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($passwordPointer)
}

Set-ItemProperty -LiteralPath "HKLM:\SYSTEM\CurrentControlSet\Services\$ServiceName" `
    -Name DelayedAutostart -Type DWord -Value 1

& sc.exe description $ServiceName 'RSB lab service that checks a retired inventory share; intentionally vulnerable to LLMNR/NBNS poisoning.' | Out-Null

# Provide a credential-gated landing path after the learner cracks the response.
Enable-PSRemoting -Force -SkipNetworkProfileCheck
Get-NetFirewallRule -DisplayGroup 'Windows Remote Management' -ErrorAction SilentlyContinue |
    Disable-NetFirewallRule -ErrorAction SilentlyContinue
$ruleName = 'RSB-CHALLENGE-WINRM'
Get-NetFirewallRule -Name $ruleName -ErrorAction SilentlyContinue | Remove-NetFirewallRule
New-NetFirewallRule -Name $ruleName -DisplayName 'RSB Challenge - WinRM from VLAN10/VPN' `
    -Group 'RSB ICS Lab' -Direction Inbound -Action Allow -Enabled True -Profile Any `
    -Protocol TCP -LocalPort 5985 -RemoteAddress $WinRmRemoteAddress | Out-Null

Start-Service -Name $ServiceName
Start-Sleep -Seconds 3

[pscustomobject]@{
    Computer = $env:COMPUTERNAME
    Service = (Get-Service -Name $ServiceName).Status
    ServiceStartName = (Get-CimInstance Win32_Service -Filter "Name='$ServiceName'").StartName
    Account = "$env:COMPUTERNAME\$ServiceAccountName"
    LocalAdministrator = [bool](Get-LocalGroupMember -SID 'S-1-5-32-544' -ErrorAction SilentlyContinue |
        Where-Object Name -eq "$env:COMPUTERNAME\$ServiceAccountName")
    RemoteManagementUser = $true
    LlmnrEnabled = (Get-ItemPropertyValue -LiteralPath $dnsPolicy -Name EnableMulticast) -eq 1
    NetbiosOptions = @(Get-CimInstance Win32_NetworkAdapterConfiguration -Filter 'IPEnabled=TRUE' |
        Select-Object Index, Description, TcpipNetbiosOptions)
    MissingTarget = "\\$MissingHost\$MissingShare"
    IntervalSeconds = $IntervalSeconds
    WinRmRule = $ruleName
    LogPath = $logPath
} | ConvertTo-Json -Depth 5
