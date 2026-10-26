#requires -RunAsAdministrator
[CmdletBinding()]
param([switch]$TestTemporaryCorporateClient)
# The optional Corporate test requires 10.0.10.20 to be unused in this lab.
$ErrorActionPreference='Stop'
$role=$env:COMPUTERNAME
$source=switch ($role) {'RSB-WS01' {'10.0.10.3'} 'RSB-WS02' {'10.0.40.12'} 'RSB-WS03' {'10.0.20.11'} default {throw 'Run only on an RSB workstation.'}}
function Test-PathRow([string]$From,[string]$To,[int]$Port,[bool]$Expected) {
    $client=[Net.Sockets.TcpClient]::new([Net.IPEndPoint]::new([Net.IPAddress]::Parse($From),0))
    $connected=$false
    try {$task=$client.ConnectAsync($To,$Port); $connected=$task.Wait(2000) -and $client.Connected} catch {} finally {$client.Dispose()}
    [pscustomobject]@{Source=$From;Destination=$To;Port=$Port;Connected=$connected;Expected=$Expected} | ConvertTo-Json -Compress
    if ($connected -ne $Expected) {throw "Unexpected connection result: $From -> ${To}:$Port"}
}
switch ($role) {
    'RSB-WS01' {
        $rows=@(@('10.0.20.20',1880),@('10.0.40.10',1881),@('10.0.40.20',8080),@('10.0.30.40',8088))
        foreach ($row in $rows) {Test-PathRow $source $row[0] $row[1] $true}
        Test-PathRow $source '10.0.50.101' 502 $false
        if ($TestTemporaryCorporateClient) {
            $temporary='10.0.10.20'
            if (Get-NetIPAddress -IPAddress $temporary -ErrorAction SilentlyContinue) {throw 'Temporary client address already exists; refusing to change it.'}
            $nic=(Get-NetIPAddress -IPAddress $source).InterfaceIndex
            New-NetIPAddress -InterfaceIndex $nic -IPAddress $temporary -PrefixLength 24 -SkipAsSource $true | Out-Null
            try {
                for ($i=0;$i -lt 20;$i++) {
                    $address=Get-NetIPAddress -InterfaceIndex $nic -IPAddress $temporary
                    if ($address.AddressState -eq 'Preferred') {break}
                    if ($address.AddressState -eq 'Duplicate') {throw 'Temporary client address is already in use.'}
                    Start-Sleep -Seconds 1
                }
                if ($address.AddressState -ne 'Preferred') {throw 'Temporary client address did not become ready.'}
                foreach ($row in $rows) {Test-PathRow $temporary $row[0] $row[1] ($row[1] -eq 8088)}
            } finally {Remove-NetIPAddress -InterfaceIndex $nic -IPAddress $temporary -Confirm:$false}
        }
    }
    'RSB-WS03' {
        Test-PathRow $source '10.0.40.12' 3389 $true
        Test-PathRow $source '10.0.40.12' 445 $false
        Test-PathRow $source '10.0.10.2' 53 $true
        Test-PathRow $source '10.0.50.101' 502 $false
        Test-PathRow $source '10.0.50.116' 20000 $false
    }
    'RSB-WS02' {
        Test-PathRow $source '10.0.50.101' 502 $true
        Test-PathRow $source '10.0.50.101' 8080 $true
        Test-PathRow $source '10.0.50.116' 20000 $true
        Test-PathRow $source '10.0.30.30' 3000 $true
        Test-PathRow $source '10.0.10.2' 445 $true
        Test-PathRow $source '10.0.20.20' 1880 $false
    }
}
