[CmdletBinding(SupportsShouldProcess)]
param()

# Keep a lab host reachable: stop it sleeping/hibernating when idle and stop
# Windows powering down the network adapters to save power. Safe to run on any
# RSB Windows host (RSB-WS01, RSB-WS03, ...). Run elevated.

$ErrorActionPreference = 'Stop'
$admin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole(
    [Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $admin) { throw 'Run this script from an elevated Windows PowerShell session.' }

# --- Never sleep / hibernate / turn off disks or display (AC and DC) ---
foreach ($m in 'ac','dc') {
    foreach ($setting in @(
        @('standby','29f6c1db-86da-48c5-9fdb-f2b67b1f44da'),
        @('hibernate','9d7815a6-7ee4-497e-8888-515a05f02364'))) {
        $policy = Get-ItemPropertyValue -LiteralPath ("HKLM:\Software\Policies\Microsoft\Power\PowerSettings\" + $setting[1]) `
            -Name ($m.ToUpper() + 'SettingIndex') -ErrorAction SilentlyContinue
        if ($null -ne $policy) {
            if ($policy -ne 0) { throw "Group policy enforces a nonzero $($setting[0]) timeout. Update the lab GPO first." }
        } else {
            & powercfg.exe "/change" "$($setting[0])-timeout-$m" 0 | Out-Null
        }
    }
    & powercfg.exe "/change" "disk-timeout-$m" 0 | Out-Null
    & powercfg.exe "/change" "monitor-timeout-$m" 0 | Out-Null
}
& powercfg.exe "/hibernate" "off" | Out-Null
Write-Host 'Power: sleep/hibernate/disk/monitor timeouts set to never (AC+DC).'

# --- Stop the OS powering down NICs ("Allow the computer to turn off this
#     device to save power"). Applies to all physical, up adapters. ---
$done = 0
foreach ($a in (Get-NetAdapter -Physical -ErrorAction SilentlyContinue)) {
    try {
        Disable-NetAdapterPowerManagement -Name $a.Name -NoRestart -ErrorAction Stop
        $done++
    } catch {
        Write-Warning "Adapter '$($a.Name)': could not set power management ($($_.Exception.Message))"
    }
}
Write-Host "NIC power management disabled on $done adapter(s)."
Write-Host 'Done. Host should now stay reachable while idle.'
