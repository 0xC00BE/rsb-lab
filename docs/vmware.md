# VMware reference build

Create a separate lab folder and resource pool. Use a new virtual switch without
physical uplinks and five dedicated port groups for Corporate, DMZ, Operations,
Engineering and Field. VLAN IDs 10/20/30/40/50 may be used inside that switch.
Record the existing network and VM configuration before starting; do not edit
existing switches, port groups, templates or running guests.

The reference fleet contains a firewall, a Docker guest, AD/DNS and three Windows
workstations. Use the sizes in [requirements](requirements.md). Keep resource
reservations at zero and choose limits/shares appropriate to the shared host.
No private vCenter addresses, inventory IDs or credentials belong in this repository.

## Network adapters

The firewall needs five lab adapters and may use a sixth adapter temporarily for
installer downloads. Identify its interfaces by MAC address. FreeBSD `vmx` order
can differ from the adapter order displayed by vCenter. Assign the logical
interfaces and gateways in [networking](networking.md), then apply the policy.
Disable DHCP on the five lab zones; the reference machines have static addresses.

The Docker guest has four OT adapters and an optional temporary build adapter.
Give the OT adapters stable names or record them in `.env`. Do not assign the
host ordinary IP addresses on those adapters; containers own their zone addresses.
Only the new Docker-facing port groups should receive the MAC/promiscuous-mode
permissions required by macvlan. Do not relax unrelated port groups.

Install all packages and build/pull the images while temporary build connectivity
is available. Install the host forwarding guard. Disconnect both the build
adapter and firewall WAN, including their connect-at-power-on settings, before
running the exercise. VMware guest operations remain usable without an IP route
from the preparation machine into the lab.

## Windows bases

Use licensed fresh installations or independent full clones of clean OS bases.
The reference used full clones, leaving the powered-off source templates intact.
Generalize each workstation and apply its own hostname/address before joining
the new `rs.brew` domain. Each guest and the DC must have a different private
administrator password; public exercise passwords are separate.

Two Store app packages blocked Sysprep on the reference Windows 10 clones.
After a clone-only snapshot, the supplied
`provisioning/windows/Repair-RSBCloneSysprep.ps1 -LabClone` removes only the
specific package identified by the current Sysprep error log. It requires a
prepared unattended file targeting one of the three RSB workstation names.
It refuses domain members and does not modify the source template. Verify the
resulting hostname, address and unique Windows identity after the reboot.

Follow [windows](windows.md) for AD, the workstation roles and exercise services.
Enable Windows firewall profiles, remove inherited template auto-login settings,
and disable unused template accounts on the new clones. Reboot member machines
after applying policies, then check their secure channels and RDP listeners.

## Acceptance and baseline

Use [acceptance](acceptance.md) and the supplied operational validators. Include
negative paths, actual live application values, historian writes and the low-privilege
engineering-agent result. Repeat startup checks with upstream adapters disconnected.

Once validated, shut down all six lab guests cleanly, take
coordinated powered-off snapshots, and restore them together to test recovery.
Keep those snapshots and private credentials on the operator's infrastructure;
the GitHub release contains source and documented configuration only.

For cold startup, start the firewall first, then AD/DNS and the Docker guest.
Wait for domain services before starting the Windows members. Allow the process
and historian services to settle, then run the live-value and secure-channel checks.
