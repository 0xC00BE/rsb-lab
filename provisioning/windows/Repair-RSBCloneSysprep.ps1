#requires -RunAsAdministrator
[CmdletBinding()]
param(
    [switch]$LabClone,
    [string]$UnattendPath = 'C:\Windows\Panther\unattend.xml',
    [ValidateRange(1,20)][int]$MaximumRepairs = 12
)
$ErrorActionPreference = 'Stop'
if (-not $LabClone) { throw 'This operation is only for a disposable release clone. Supply -LabClone after taking a snapshot.' }
if ([Diagnostics.Process]::GetCurrentProcess().SessionId -eq 0) {
    throw 'Run this Appx repair in an elevated interactive session of the template user that owns the packages. Guest Operations runs in session 0 and cannot reliably remove those per-user registrations.'
}
if ((Get-CimInstance Win32_ComputerSystem).PartOfDomain) { throw 'Repair the base clone before joining a domain.' }
if (-not (Test-Path -LiteralPath $UnattendPath)) { throw 'A prepared unattended customization file is required.' }
[xml]$unattend = Get-Content -Raw -LiteralPath $UnattendPath
$target = $unattend.SelectSingleNode("//*[local-name()='ComputerName']").InnerText
if ($target -notin @('RSB-WS01','RSB-WS02','RSB-WS03')) { throw 'Unattended target must be an RSB release workstation.' }
$errorLog = 'C:\Windows\System32\Sysprep\Panther\setuperr.log'
for ($attempt=1; $attempt -le $MaximumRepairs; $attempt++) {
    $lines = Get-Content -LiteralPath $errorLog -ErrorAction SilentlyContinue
    $line = @($lines | Where-Object { $_ -match 'SYSPRP Package (\S+) was installed for a user' } | Select-Object -Last 1)
    if (-not $line -or $line[0] -notmatch 'SYSPRP Package (\S+) was installed for a user') {
        throw 'No specific per-user Appx blocker was identified. Inspect the Sysprep logs; do not remove packages blindly.'
    }
    $fullName = $Matches[1]
    $package = Get-AppxPackage -AllUsers | Where-Object PackageFullName -eq $fullName
    if (-not $package) { throw "Reported blocker $fullName is no longer installed; review the latest Sysprep result." }
    if ($package.NonRemovable) { throw "Reported blocker $fullName is non-removable; use a clean base image." }
    Write-Output "Removing only the reported Appx blocker from this clone: $($package.Name)"
    Remove-AppxPackage -Package $fullName -AllUsers
    $previousErrors = Get-Content -Raw -LiteralPath $errorLog -ErrorAction SilentlyContinue
    $process = Start-Process -WindowStyle Hidden -FilePath 'C:\Windows\System32\Sysprep\sysprep.exe' `
        -ArgumentList "/quiet /generalize /oobe /reboot /unattend:$UnattendPath" -Wait -PassThru
    Start-Sleep -Seconds 5
    $currentErrors = Get-Content -Raw -LiteralPath $errorLog -ErrorAction SilentlyContinue
    # Sysprep can report process exit 0 even when validation failed. Its error
    # log is the deciding evidence; never infer successful customization here.
    if ($currentErrors -ne $previousErrors) {
        if ($currentErrors -notmatch 'SYSPRP Package (\S+) was installed for a user') {
            throw 'Sysprep reported a different failure. Inspect its logs before continuing.'
        }
        continue
    }
    if ($process.ExitCode -eq 0) {
        Write-Output 'No new Sysprep validation errors. Verify the reboot, hostname and network settings before proceeding.'
        return
    }
    throw "Sysprep exited with code $($process.ExitCode). Inspect its logs."
}
throw 'Repair limit reached. Inspect the clone logs or use a clean Windows base image.'
