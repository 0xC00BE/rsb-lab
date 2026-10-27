#requires -RunAsAdministrator
[CmdletBinding()]
param(
    [string]$ServiceAccountName='svc_engagent',
    [switch]$Reset
)
$ErrorActionPreference='Stop'
if($PSVersionTable.PSEdition -ne 'Desktop'){throw 'Use Windows PowerShell 5.1.'}
if($env:COMPUTERNAME -ne 'RSB-WS03' -or (Get-CimInstance Win32_ComputerSystem).Domain -ne 'rs.brew'){
    throw 'This fixture is restricted to the dedicated rs.brew Jump workstation.'
}
$account=Get-LocalUser -Name $ServiceAccountName -ErrorAction Stop
$adminSid=[Security.Principal.SecurityIdentifier]::new('S-1-5-32-544')
$systemSid=[Security.Principal.SecurityIdentifier]::new('S-1-5-18')
if(Get-LocalGroupMember -SID $adminSid | Where-Object {$_.SID -eq $account.SID}){
    throw 'The engineering service account must remain a non-administrator.'
}
$directory='C:\ProgramData\RSB-Lab\Maintenance'
$script=Join-Path $directory 'health.ps1'
$taskName='RSB-Lab-Maintenance'
$description='RSB lab maintenance fixture (managed by RSB role installer)'
foreach($path in @((Split-Path $directory),$directory,$script)){
    if((Test-Path -LiteralPath $path) -and ((Get-Item -LiteralPath $path -Force).Attributes -band [IO.FileAttributes]::ReparsePoint)){
        throw 'The fixture path must not contain a junction or symbolic link.'
    }
}
$existing=Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
if($existing -and $existing.Description -ne $description){throw 'An unrelated task uses the fixture name.'}
$baseline=@'
$ErrorActionPreference='Stop'
$text='Brewery maintenance ready '+[DateTime]::UtcNow.ToString('o')
[IO.File]::WriteAllText((Join-Path $PSScriptRoot 'health.txt'),$text,[Text.UTF8Encoding]::new($false))
'@
$baseline=$baseline.Replace("`r`n","`n")+"`n"
if((Test-Path -LiteralPath $script) -and -not $Reset){
    $current=[IO.File]::ReadAllText($script).Replace("`r`n","`n")
    if($current -ne $baseline){throw 'The maintenance file has changed; preserve it or use -Reset for a new baseline.'}
}
New-Item -ItemType Directory -Force -Path $directory | Out-Null
$folderAcl=[Security.AccessControl.DirectorySecurity]::new()
$folderAcl.SetAccessRuleProtection($true,$false);$folderAcl.SetOwner($adminSid)
foreach($sid in @($systemSid,$adminSid)){
    $folderAcl.AddAccessRule([Security.AccessControl.FileSystemAccessRule]::new($sid,[Security.AccessControl.FileSystemRights]::FullControl,[Security.AccessControl.InheritanceFlags]'ContainerInherit,ObjectInherit',[Security.AccessControl.PropagationFlags]::None,[Security.AccessControl.AccessControlType]::Allow))
}
$folderAcl.AddAccessRule([Security.AccessControl.FileSystemAccessRule]::new($account.SID,[Security.AccessControl.FileSystemRights]::ReadAndExecute,[Security.AccessControl.InheritanceFlags]'ContainerInherit,ObjectInherit',[Security.AccessControl.PropagationFlags]::None,[Security.AccessControl.AccessControlType]::Allow))
Set-Acl -LiteralPath $directory -AclObject $folderAcl
[IO.File]::WriteAllText($script,$baseline,[Text.UTF8Encoding]::new($false))
$fileAcl=[Security.AccessControl.FileSecurity]::new()
$fileAcl.SetAccessRuleProtection($true,$false);$fileAcl.SetOwner($adminSid)
foreach($sid in @($systemSid,$adminSid)){
    $fileAcl.AddAccessRule([Security.AccessControl.FileSystemAccessRule]::new($sid,[Security.AccessControl.FileSystemRights]::FullControl,[Security.AccessControl.AccessControlType]::Allow))
}
# Intentional, local-only exercise condition; see optional instructor material.
$fileAcl.AddAccessRule([Security.AccessControl.FileSystemAccessRule]::new($account.SID,[Security.AccessControl.FileSystemRights]::Modify,[Security.AccessControl.AccessControlType]::Allow))
Set-Acl -LiteralPath $script -AclObject $fileAcl
$action=New-ScheduledTaskAction -Execute "$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe" -Argument ('-NoProfile -NonInteractive -ExecutionPolicy Bypass -File "'+$script+'"')
$trigger=New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(1) -RepetitionInterval (New-TimeSpan -Minutes 1)
$principal=New-ScheduledTaskPrincipal -UserId 'SYSTEM' -LogonType ServiceAccount -RunLevel Highest
$settings=New-ScheduledTaskSettingsSet -StartWhenAvailable -ExecutionTimeLimit (New-TimeSpan -Seconds 30) -MultipleInstances IgnoreNew -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Principal $principal -Settings $settings -Description $description -Force | Out-Null
$scheduler=New-Object -ComObject 'Schedule.Service';$scheduler.Connect()
$registered=$scheduler.GetFolder('\').GetTask($taskName)
$registered.SetSecurityDescriptor(('D:P(A;;GA;;;SY)(A;;GA;;;BA)(A;;GRGX;;;'+$account.SID.Value+')'),0)
Write-Host 'Jump maintenance fixture installed. Its benign scheduled job runs automatically; no escalation test was run.'
