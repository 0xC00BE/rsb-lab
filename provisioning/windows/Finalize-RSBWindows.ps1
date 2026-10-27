#requires -RunAsAdministrator
[CmdletBinding()]
param([Parameter(Mandatory)][ValidateSet('AD','Corporate','Jump','Engineering')][string]$Role)
$ErrorActionPreference='Stop'
$expected=@{AD='RSBAD01';Corporate='RSB-WS01';Jump='RSB-WS03';Engineering='RSB-WS02'}
if($env:COMPUTERNAME -ne $expected[$Role] -or (Get-CimInstance Win32_ComputerSystem).Domain -ne 'rs.brew'){throw 'Run only on the selected dedicated lab guest.'}
$winlogon='HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Winlogon'
Set-ItemProperty -LiteralPath $winlogon -Name AutoAdminLogon -Value '0'
Remove-ItemProperty -LiteralPath $winlogon -Name DefaultPassword -ErrorAction SilentlyContinue
Remove-ItemProperty -LiteralPath $winlogon -Name AutoLogonCount -ErrorAction SilentlyContinue
if($Role -ne 'AD'){
    foreach($name in @('W10User','smb')){
        $templateUser=Get-LocalUser -Name $name -ErrorAction SilentlyContinue
        if($templateUser){Disable-LocalUser -SID $templateUser.SID}
    }
}
# Remove only known unattended answer files from this completed clone.
foreach($path in @('C:\Windows\Panther\unattend.xml','C:\Windows\System32\Sysprep\unattend.xml','C:\Windows\Temp\vmware-imc\unattend.xml')){
    if(Test-Path -LiteralPath $path){
        $item=Get-Item -LiteralPath $path -Force
        if($item.PSIsContainer -or ($item.Attributes -band [IO.FileAttributes]::ReparsePoint)){throw 'Unexpected unattended-file type; inspect before cleanup.'}
        Remove-Item -LiteralPath $item.FullName -Force
    }
}
Set-NetFirewallProfile -Profile Domain,Private,Public -Enabled True
Write-Host "Finalized ${Role}: template auto-login disabled and known answer files removed."
