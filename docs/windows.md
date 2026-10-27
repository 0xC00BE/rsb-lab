# Windows installation

Use fresh Windows installations or independent full clones of clean OS bases.
Supply your own Windows media and licensing. See [vmware.md](vmware.md) for the
tested layout and clone customization requirements.

## Build order

1. Rename the server `RSBAD01`, reboot, and configure `10.0.10.2/24`, gateway
   `10.0.10.1`, DNS `10.0.10.2`. Run
   `provisioning/windows/New-LabDomain.ps1` elevated, choose a private recovery
   password, and allow the promotion reboot.
2. Configure the three members using the table below. Set their DNS server to
   `10.0.10.2`, join `rs.brew` with your private domain administrator account,
   and reboot. Wait for AD/DNS before joining members.
3. Copy the repository to an administrator-only staging directory on each Windows
   guest, preserving its layout. For example, protect
   `C:\ProgramData\RSB-Lab\Setup\Source` for SYSTEM/Administrators before extracting.
   In elevated **Windows PowerShell 5.1**, run the role installer on the DC first,
   after all three members have joined:

   ```powershell
   .\provisioning\windows\Install-RSBRole.ps1 -Role AD
   ```

4. Run the same installer on each member with its role:

   ```powershell
   # On RSB-WS01
   .\provisioning\windows\Install-RSBRole.ps1 -Role Corporate
   # On RSB-WS03
   .\provisioning\windows\Install-RSBRole.ps1 -Role Jump
   # On RSB-WS02
   .\provisioning\windows\Install-RSBRole.ps1 -Role Engineering
   ```

   The Jump installer prompts for a new private local service password and the
   Docker guest's generated `MQTT_PASSWORD`. Keep these out of public files.
   Setup logs are restricted to administrators and SYSTEM under
   `C:\ProgramData\RSB-Lab\Setup`.
5. Apply domain policy and reboot members. Give every guest a unique private
   administrator password. Remove inherited template auto-login settings and
   disable unused template accounts. Keep all Windows firewall profiles enabled.
   `Finalize-RSBWindows.ps1 -Role Corporate` (using the correct role) performs the
   known template auto-login/account and answer-file cleanup. Remove private
   bootstrap files and staged source after installation; preserve runtime files.
6. Complete [installation acceptance](acceptance.md). Use a separate Corporate
   client for exercises, or the optional [student VPN](vpn.md).

Check each guest with `tools/validate/windows.ps1 -Role Corporate`, substituting
its role. Add `-RequireVpnManagement` when the optional VPN host adapter is
installed. The check waits for delayed automatic services rather than treating
the normal Windows startup delay as a failure.

| Guest | Role | Address | Gateway |
|---|---|---|---|
| RSBAD01 | AD | 10.0.10.2/24 | 10.0.10.1 |
| RSB-WS01 | Corporate | 10.0.10.3/24 | 10.0.10.1 |
| RSB-WS03 | Jump | 10.0.20.11/24 | 10.0.20.1 |
| RSB-WS02 | Engineering | 10.0.40.12/24 | 10.0.40.1 |

These scripts configure the supplied training scenario. Run them only in a
dedicated lab domain, not on organizational workstations.

## Optional instructor material — spoilers

Installation does not require reading the solution. Detailed scenario behavior,
account references and assessment checks are in the optional
[instructor guide](../exercises/instructor/guide.md). Reading it reveals solutions.
