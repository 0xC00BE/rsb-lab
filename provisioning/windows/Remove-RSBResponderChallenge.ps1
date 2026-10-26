[CmdletBinding(SupportsShouldProcess, ConfirmImpact = 'High')]
param(
    [string]$ServiceName = 'RSBInventorySync',
    [string]$ServiceAccountName = 'svc_inventory',
    [switch]$KeepLocalUser
)

$ErrorActionPreference = 'Stop'
$installRoot = 'C:\ProgramData\RSB-Lab\ResponderChallenge'
$baselinePath = Join-Path $installRoot 'baseline.json'

if ($PSCmdlet.ShouldProcess($env:COMPUTERNAME, 'Remove the RSB Responder challenge service and restore name-resolution settings')) {
    Get-Service -Name $ServiceName -ErrorAction SilentlyContinue |
        Stop-Service -Force -ErrorAction SilentlyContinue
    if (Get-Service -Name $ServiceName -ErrorAction SilentlyContinue) {
        & sc.exe delete $ServiceName | Out-Null
        Start-Sleep -Seconds 2
    }

    Get-NetFirewallRule -Name 'RSB-CHALLENGE-WINRM' -ErrorAction SilentlyContinue |
        Remove-NetFirewallRule

    if (Test-Path -LiteralPath $baselinePath) {
        $baseline = Get-Content -LiteralPath $baselinePath -Raw | ConvertFrom-Json
        $dnsPolicy = 'HKLM:\Software\Policies\Microsoft\Windows NT\DNSClient'
        if ($null -eq $baseline.LlmnrEnableMulticast) {
            Remove-ItemProperty -LiteralPath $dnsPolicy -Name EnableMulticast -ErrorAction SilentlyContinue
        } else {
            Set-ItemProperty -LiteralPath $dnsPolicy -Name EnableMulticast -Type DWord `
                -Value ([int]$baseline.LlmnrEnableMulticast)
        }
        foreach ($saved in $baseline.Netbios) {
            $adapter = Get-CimInstance Win32_NetworkAdapterConfiguration -Filter "Index=$($saved.Index)" -ErrorAction SilentlyContinue
            if ($adapter) {
                Invoke-CimMethod -InputObject $adapter -MethodName SetTcpipNetbios `
                    -Arguments @{ TcpipNetbiosOptions = [uint32]$saved.TcpipNetbiosOptions } | Out-Null
            }
        }

        foreach ($savedRule in @($baseline.WinRmFirewallRules)) {
            $rule = Get-NetFirewallRule -Name $savedRule.Name -ErrorAction SilentlyContinue
            if ($rule) {
                if ($savedRule.Enabled -eq 1 -or $savedRule.Enabled -eq 'True') {
                    $rule | Enable-NetFirewallRule
                } else {
                    $rule | Disable-NetFirewallRule
                }
            }
        }

        $winRmStartup = switch ($baseline.WinRmStartType) {
            'Auto' { 'Automatic' }
            'Manual' { 'Manual' }
            'Disabled' { 'Disabled' }
            default { 'Manual' }
        }
        Set-Service -Name WinRM -StartupType $winRmStartup
        if ($baseline.WinRmState -eq 'Stopped') {
            Stop-Service -Name WinRM -Force -ErrorAction SilentlyContinue
        }
    }

    if (-not $KeepLocalUser) {
        Get-LocalUser -Name $ServiceAccountName -ErrorAction SilentlyContinue |
            Remove-LocalUser
    }

    # Retain baseline.json and the log as rollback evidence; remove only the executable.
    $binaryPath = Join-Path $installRoot 'RSBInventorySync.exe'
    if (Test-Path -LiteralPath $binaryPath) {
        Remove-Item -LiteralPath $binaryPath -Force
    }
}

[pscustomobject]@{
    ServicePresent = [bool](Get-Service -Name $ServiceName -ErrorAction SilentlyContinue)
    AccountPresent = [bool](Get-LocalUser -Name $ServiceAccountName -ErrorAction SilentlyContinue)
    EvidenceDirectory = $installRoot
} | Format-List
