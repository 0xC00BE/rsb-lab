# Detailed Windows setup — spoilers

Archived technical setup reference. Use [the ordinary installation guide](../../docs/windows.md) for spoiler-free setup.

# Full Windows lab

This guide combines the supplied configuration scripts with manual OS provisioning.
Windows media, activation, unattended installs, domain joining, and VM creation are
not automated by this source preview. Use editions supporting AD domain join;
review the terms of your own media. Do not distribute activated private VM disks.

## Build order

1. Install a fresh server, rename it `RSBAD01`, reboot, and assign
   `10.0.10.2/24`, gateway `10.0.10.1`. Install only on the isolated Corporate zone.
   Set its DNS to its own address. Run `provisioning/windows/New-LabDomain.ps1`
   elevated; choose a private DSRM password and allow the promotion reboot.
2. Install the three workstation guests, rename and address them as below, and
   set DNS to **10.0.10.2**, not the hypervisor/router or an external resolver.
   Join `rs.brew` using your private domain administrator credential, then reboot.
   The reference firewall allows the two remote-zone workstation addresses to AD.
3. Copy the repository to each machine, preserving the `lab/` and `provisioning/`
   relationship. On the DC, run `Implement-RSBAD.ps1` elevated after joining all
   three workstations. It creates lab OUs, groups, accounts and deliberate
   membership/share weaknesses, then moves the existing computer objects.
   Run `Configure-RSBReachabilityAndNTLM-GPO.ps1` and
   `Configure-RSBResponderChallengeGPO.ps1`. These deliberately permit the NTLM
   and name-resolution behavior used by the initial-access exercise.
4. On WS03 run `Configure-RSBWorkstation.ps1 -Role Jump`; on WS02 use
   `-Role Engineering`. Stage Windows firewall rules on all four Windows guests
   with `Stage-RSBFirewallRules.ps1 -Role AD|Corporate|Jump|Engineering`, choosing
   the role for that host. These scripts add rules; they do not remove unrelated
   existing allows or validate your effective GPO firewall policy.
   Enable all Windows firewall profiles on the new lab guests. Use a different
   private administrator password on each workstation and the DC. Remove inherited
   auto-login settings and disable unused template users on the clones.
5. On WS01 run `Stage-PublicClues.ps1 -Role Corporate` and
   `Install-RSBResponderChallenge.ps1` in **Windows PowerShell 5.1** elevated.
   For the local `svc_inventory` account use the public exercise example
   **Password1!** if you want the documented initial-access exercise. This is
   deliberately weak and is not a private administration credential.
   Leave `RSB-FILE-OLD` absent from DNS and hosts files. Apply `gpupdate /force`.
6. On WS03 run `Stage-PublicClues.ps1 -Role Jump` and the MQTT agent installer
   under `provisioning/windows/mqtt-agent/`. Supply a new local service-account
   password and the locally generated `MQTT_PASSWORD` from the Docker host.
   The installer compiles the supplied C# source using the built-in compiler.
7. Configure an optional attack VM as `10.0.10.20/24`, gateway `.1`. Attach it
   directly to Corporate, because LLMNR/NBNS broadcasts do not cross routers.
   Run the AD, Responder and agent test scripts and the network acceptance checks.
   Reboot members after applying GPOs and verify their domain secure channels.
   `Test-RSBNetworkPaths.ps1` checks the intended workstation paths. Its optional
   temporary Corporate client test requires `.10.20` to be unused; it removes
   that secondary address afterward.

| Guest | Address | Gateway |
|---|---|---|
| RSBAD01 | 10.0.10.2/24 | 10.0.10.1 |
| RSB-WS01 | 10.0.10.3/24 | 10.0.10.1 |
| RSB-WS03 | 10.0.20.11/24 | 10.0.20.1 |
| RSB-WS02 | 10.0.40.12/24 | 10.0.40.1 |

The reference scripts use `10.0.10.254` as an optional administrator station in
Corporate, replacing the private lab's VPN address. You must create this station
yourself if you need it. It is distinct from the Docker guest's per-zone host
shims. The examples do not enable or ship a VPN.

## Intentional weaknesses

The inventory service provokes name-resolution authentication from WS01; a
readable local app configuration contains a public domain user's credential.
Domain group/share permissions expose the Node-RED deployment credential.
The authenticated Node-RED editor can send MQTT jobs to the WS03 agent, whose
intentional `exec` job runs commands as a low-privilege local account. A restricted
engineering handoff contains the public engineer identity. These are training
features, not secure deployment patterns.

The public service-account examples use `PublicLab!AppNN`. They deliberately
avoid a display-name token such as `Service`, which Windows password complexity
can reject even when the password has sufficient character classes.

Windows security updates can change local escalation behavior. No third-party
escalation tools or vulnerable Windows images are bundled, and a particular
local escalation exploit is not guaranteed. Verify the full path on your chosen
build before giving an assessed exercise. Current public source scripts use
`henrik.solberg`; later private runbooks naming a different engineer are not part
of this reference build.

Do not run these scripts on an existing organizational domain. They change
passwords, group memberships, GPOs, local services, firewall rules, and staged
credential clues. Inspect their source before applying them to your dedicated lab.
