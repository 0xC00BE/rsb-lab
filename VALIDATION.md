# VMware reference validation

Date: 2026-10-26. Scope: the primary reference lab and a second, independently
created six-VM fleet on the authorized VMware host. The second fleet used repository
files, fresh private state and clean OS bases. Its firewall base was reset to vendor
defaults and stripped of prior lab/VPN/operator state before repository bootstrap.
Original lab machines, source templates and outside networking remained unchanged.

## Dashboard correction — 2026-10-27 (v0.1.1)

Read-only exports from the current production HMI and SCADA confirmed that the
active project contains only Dashboard-P1 through P4. The HMI visual definitions
were bundled with their 26 unique PNG assets (38 embedded references). Existing
release device definitions matched exactly. Production configuration was unchanged.
The release copy fixes a deleted start-view reference and the P4 menu spelling.

Both running release-lab roles were upgraded using `tools/update_fuxa.py --apply`.
Each old 26-view project was backed up privately, replaced with the four current
dashboards, and verified by authenticated readback. Editor credentials remained
unchanged. All eight headless dashboard renders passed; all referenced images
decoded, no browser errors occurred, and external requests were blocked. All four
HMI screenshots were visually inspected and replaced the old gallery. P1 contains
two unused empty image elements from production; these have no image source.

The six Modbus connections returned live values on both roles; HMI BACnet also
returned live values. Anonymous value writes remained rejected. Local source
validation and 19 unit tests passed, including known-legacy migration acceptance
and refusal of an unknown custom dashboard. The earlier full VMware build and
recovery evidence below belongs to v0.1.0; it was not repeated for this visual update.
The Jump-host escalation exclusion remains unchanged.

## Tested combination

- vCenter Server 8.0.3 build 24262322; ESXi 8.0.0 build 20513097; x86-64 guests.
- Ubuntu 24.04 LTS, Docker Engine 29.1.3 and Compose 2.40.3+ds1. Docker guest:
  6 vCPU, 12 GiB RAM and 120 GiB virtual disk. These are tested allocations.
- pfSense CE 2.9.0 and native OpenVPN 2.7.5; five isolated lab zones and optional WAN.
- Windows Server 2019 build 17763 and three Windows 10 Pro build 19045 guests.
  OS media/bases and licensing are operator supplied.
- Image references and source commit in `lab/upstreams.lock.json`, with committed
  FUXA, Node-RED and optional browser npm lock files.

## Independent source build

The VMware provider created six independent full OS clones, a new folder/resource
pool and isolated port groups on a switch without uplinks. TLS pinning rejected
an incorrect certificate. Ownership and repeated inventory audits protected existing
resources. Guest customization used vCenter and guest operations; no user desktop
was needed. Legacy Windows Appx repair required the clone's interactive VM session.

All image builds completed from repository files. Six PLC programs compiled,
started and retained automatic startup. Fresh application state, credentials,
projects and directory roles were generated without a runtime configuration donor.

- In v0.1.0, both FUXA roles imported all 26 older views and 47 bundled artwork assets. All **52
  headless renders** passed: expected images decoded, external HTTP requests were
  blocked, no page errors or known encoding artifacts occurred. Selected layouts
  were visually inspected; examples are in the [gallery](docs/gallery.md).
- Six PLCs and HMI BACnet returned live values. Anonymous project saves/value
  writes were rejected. Scada-LTS imported eight sources/159 points; all 17 enabled
  native BACnet/DNP3 points had stored samples.
- All 21 application containers were running without unhealthy status. Six
  historian measurement groups and all eight Grafana panels returned recent data.
  The three status indicators were clean with live telemetry.
- A new domain and three members passed service, secure-channel and firewall
  checks. All four Windows identities were distinct. Template auto-login and
  unused template accounts were disabled; known private bootstrap files were removed.
- Authenticated Node-RED injection reached the engineering agent. Its result
  showed the intended non-administrator identity and denied protected handoff access.
  **The new Jump extension's escalation path was excluded from live testing.**
  Its installer completed; no escalation payload or escalation proof was run.
- Declared application paths worked, representative undeclared paths failed,
  and the explicit Docker-host forwarding bypass was rejected.

## VPN and containment

Fresh administrator and student identities authenticated from WAN using separate
certificate authorities. The administrator reached management/application paths
across all five zones. The student reached the intended Corporate services/status
board while representative firewall and OT management paths were blocked.
A disposable identity connected before revocation and was rejected afterward.
Both normal roles passed again after native firewall reboot with setup access removed.

Direct WAN TCP 22/80/443/2222 remained blocked. A live ARP response from the exact
recorded firewall MAC established that negative checks used a reachable peer;
the checks completed before disconnecting their test adapter. Temporary firewall
SSH, its key/rule, private bootstrap media and live copied client keys were removed.

Additional component checks on the primary reference lab verified Corporate LLMNR,
all eight Corporate/Jump callback paths, rejection of a student identity at the
administrator listener, all-four-Windows admin RDP/WinRM/SMB paths, and both-role
forwarding blocks to a controlled upstream endpoint with a positive direct baseline.

## Offline startup and recovery

The independent fleet passed offline cold startup with both upstream adapters
disconnected. Domain/services, live application values, historian panels and
network isolation returned. Three harmless post-baseline markers were then created
on Linux, Jump and firewall; restoring all six powered-off snapshots removed all
three. Domain secure channels and application health recovered, while native VPN
configuration/revocation persisted and temporary access remained absent.

The temporary build adapter was made optional so disconnected DHCP does not hold
up offline startup. A separate Linux reboot verified approximately 9.9 seconds for
system startup on the tested allocation; application health was checked after
services settled. The final independent fleet was preserved powered off.

Local source validation and **18 unit tests** passed. All **23 PowerShell sources**
parsed. GitHub Actions checks source, unit tests, Compose interpolation and Windows
syntax before publication; the release PR/Actions records the hosted outcome.

## Practical limits

This covers the stated VMware reference and representative paths, not every
possible flow or attack outcome. The new escalation behavior is explicitly
untested. Proxmox and other platforms are not certified. Initial builds require
internet access; dependency pins do not promise bit-identical future builds or
a complete image vulnerability/license audit.

Optional [instructor acceptance](exercises/instructor/acceptance.md) contains
scenario details. Public source and older releases can reveal solutions. Private
credentials, management addresses, inventory IDs and raw captures are excluded.
