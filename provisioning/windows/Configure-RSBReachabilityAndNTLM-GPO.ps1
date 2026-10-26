#requires -Modules GroupPolicy, ActiveDirectory
[CmdletBinding(SupportsShouldProcess)]
param(
    [string]$GpoName = 'RSB - Host Reachability and WinRM NTLM',
    # Where to link the GPO. Default: the domain root (covers all computers).
    # Pass an OU DN (e.g. 'OU=Workstations,OU=RSB,DC=rs,DC=brew') to scope it.
    [string]$TargetDN
)

# =============================================================================
# Run this ON the domain controller (RSBAD01) as Domain Admin.
#
# Creates / updates a GPO that, domain-wide:
#   1. Stops computers sleeping/hibernating when idle (keeps hosts reachable).
#   2. Stops Windows powering down network adapters (startup script).
#   3. Re-allows NTLM so WinRM (and SMB) accept NTLM authentication.
#
# SECURITY NOTE: re-enabling NTLM lowers security. That is intentional here:
# this is an isolated, deliberately vulnerable training lab, and the initial-
# access scenario (Responder NTLM capture) depends on NTLM being available.
# Do NOT run this on a production domain.
# =============================================================================

$ErrorActionPreference = 'Stop'
Import-Module GroupPolicy
Import-Module ActiveDirectory

$domainDns = $env:USERDNSDOMAIN
if (-not $domainDns) { $domainDns = (Get-ADDomain).DNSRoot }
$domainDN  = (Get-ADDomain).DistinguishedName
if (-not $TargetDN) { $TargetDN = $domainDN }

Write-Host "Domain: $domainDns  ($domainDN)"
Write-Host "GPO   : $GpoName"
Write-Host "Link  : $TargetDN"

# --- Create or reuse the GPO ------------------------------------------------
$gpo = Get-GPO -Name $GpoName -ErrorAction SilentlyContinue
if (-not $gpo) { $gpo = New-GPO -Name $GpoName -Comment 'RSB lab: reachability (no sleep / NIC power) + WinRM NTLM.' }
$gpoId = $gpo.Id.Guid

# --- 1. Power: never sleep / hibernate (AC + DC) via policy registry ---------
$power = 'HKLM\Software\Policies\Microsoft\Power\PowerSettings'
$standby  = "$power\29f6c1db-86da-48c5-9fdb-f2b67b1f44da"  # Sleep after
$hibernate= "$power\9d7815a6-7ee4-497e-8888-515a05f02364"  # Hibernate after
foreach ($k in $standby, $hibernate) {
    Set-GPRegistryValue -Name $GpoName -Key $k -ValueName ACSettingIndex -Type DWord -Value 0 | Out-Null
    Set-GPRegistryValue -Name $GpoName -Key $k -ValueName DCSettingIndex -Type DWord -Value 0 | Out-Null
}

# --- 2. Re-allow NTLM (LSA + Netlogon) --------------------------------------
$msv = 'HKLM\SYSTEM\CurrentControlSet\Control\Lsa\MSV1_0'
Set-GPRegistryValue -Name $GpoName -Key $msv -ValueName RestrictReceivingNTLMTraffic -Type DWord -Value 0 | Out-Null  # Allow all
Set-GPRegistryValue -Name $GpoName -Key $msv -ValueName RestrictSendingNTLMTraffic   -Type DWord -Value 0 | Out-Null  # Allow all
$netlogon = 'HKLM\SYSTEM\CurrentControlSet\Services\Netlogon\Parameters'
Set-GPRegistryValue -Name $GpoName -Key $netlogon -ValueName RestrictNTLMInDomain -Type DWord -Value 0 | Out-Null       # No domain NTLM restriction
# Allow remote administration by LOCAL accounts over the network (otherwise UAC
# token filtering rejects remote NTLM logons by local admins, e.g. W10User).
$sysPol = 'HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\Policies\System'
Set-GPRegistryValue -Name $GpoName -Key $sysPol -ValueName LocalAccountTokenFilterPolicy -Type DWord -Value 1 | Out-Null
# Accept NTLMv2, refuse LM/NTLMv1 (5). Leaves NTLMv2 working for WinRM/SMB.
$lsaKey = 'HKLM\SYSTEM\CurrentControlSet\Control\Lsa'
Set-GPRegistryValue -Name $GpoName -Key $lsaKey -ValueName LmCompatibilityLevel -Type DWord -Value 5 | Out-Null

# --- 3. WinRM service: auto-config + accept connections from any source ------
$winrmSvc = 'HKLM\Software\Policies\Microsoft\Windows\WinRM\Service'
Set-GPRegistryValue -Name $GpoName -Key $winrmSvc -ValueName AllowAutoConfig -Type DWord  -Value 1   | Out-Null
Set-GPRegistryValue -Name $GpoName -Key $winrmSvc -ValueName IPv4Filter      -Type String -Value '*' | Out-Null
Set-GPRegistryValue -Name $GpoName -Key $winrmSvc -ValueName IPv6Filter      -Type String -Value '*' | Out-Null

# --- 4. Computer startup script: NIC power + WinRM Negotiate belt-and-braces -
# The NIC "allow the computer to turn off this device" setting is per-adapter,
# so it is applied imperatively at boot rather than by a static registry value.
$startupScript = @'
# RSB lab: keep host reachable. Runs as SYSTEM at boot.
foreach ($a in (Get-NetAdapter -Physical -ErrorAction SilentlyContinue)) {
    try { Disable-NetAdapterPowerManagement -Name $a.Name -NoRestart -ErrorAction Stop } catch {}
}
foreach ($m in 'ac','dc') {
    # Sleep/hibernate timeouts are already enforced by this GPO. Repeating
    # their local setters produces a policy-override error on Windows 10.
    & powercfg.exe /change "monitor-timeout-$m" 0
    & powercfg.exe /change "disk-timeout-$m" 0
}
& powercfg.exe /hibernate off
try { Enable-PSRemoting -Force -SkipNetworkProfileCheck -ErrorAction SilentlyContinue | Out-Null } catch {}
try { & winrm.cmd set winrm/config/service/auth '@{Negotiate="true"}' | Out-Null } catch {}
'@

$sysvolPol  = "\\$domainDns\SYSVOL\$domainDns\Policies\{$gpoId}"
$startupDir  = Join-Path $sysvolPol 'Machine\Scripts\Startup'
$scriptsRoot = Join-Path $sysvolPol 'Machine\Scripts'
New-Item -ItemType Directory -Path $startupDir -Force | Out-Null
Set-Content -LiteralPath (Join-Path $startupDir 'RSB-StayAwake.ps1') -Value $startupScript -Encoding UTF8

# psscripts.ini registers PowerShell startup scripts (must be Unicode).
$psscripts = @"
[Startup]
0CmdLine=RSB-StayAwake.ps1
0Parameters=
"@
Set-Content -LiteralPath (Join-Path $scriptsRoot 'psscripts.ini') -Value $psscripts -Encoding Unicode
# Mark the ini hidden/system like the GPMC does (best effort).
try { (Get-Item (Join-Path $scriptsRoot 'psscripts.ini') -Force).Attributes = 'Hidden,System' } catch {}

# --- 5. Register the Scripts CSE and bump the GPO version --------------------
# gPCMachineExtensionNames must advertise both the Registry CSE (already added
# by Set-GPRegistryValue) and the Scripts CSE, sorted by the first GUID.
$registryCse = '{35378EAC-683F-11D2-A89A-00C04FBBCFA2}{D02B1F72-3407-48AE-BA88-E8213C6761F1}'
$scriptsCse  = '{42B5FAAE-6536-11D2-AE5A-0000F87571E3}{40B6664F-4972-11D1-A7CA-0000F87571E3}'
$gpoAdPath = "CN={$gpoId},CN=Policies,CN=System,$domainDN"
Set-ADObject -Identity $gpoAdPath -Replace @{ gPCMachineExtensionNames = "[$registryCse][$scriptsCse]" }

# Increment the computer-side version (high word) in AD and GPT.INI so clients
# re-apply after the manual SYSVOL change.
$adObj = Get-ADObject -Identity $gpoAdPath -Properties versionNumber
$newVersion = [int]$adObj.versionNumber + 65536
Set-ADObject -Identity $gpoAdPath -Replace @{ versionNumber = $newVersion }
$gptIni = Join-Path $sysvolPol 'GPT.INI'
@("[General]", "Version=$newVersion") | Set-Content -LiteralPath $gptIni -Encoding ASCII

# --- 6. Link the GPO if not already linked ----------------------------------
$linked = (Get-GPInheritance -Target $TargetDN).GpoLinks | Where-Object { $_.GpoId -eq $gpoId }
if (-not $linked) { New-GPLink -Guid $gpoId -Target $TargetDN -LinkEnabled Yes -Enforced Yes | Out-Null; Write-Host 'GPO linked (enforced).' }
else { Set-GPLink -Guid $gpoId -Target $TargetDN -LinkEnabled Yes -Enforced Yes | Out-Null; Write-Host 'GPO link set to enforced.' }
# Enforced so these settings win over any OU-linked hardening GPO that restricts NTLM.

Write-Host ''
Write-Host "Done. GPO '$GpoName' configured and linked at $TargetDN (version $newVersion)."
Write-Host 'Apply on the hosts with:  gpupdate /force   (NIC/startup-script parts take effect at next REBOOT).'
Write-Host 'Then confirm WinRM NTLM, e.g. from a client:  Test-WSMan -ComputerName 10.0.20.11'
