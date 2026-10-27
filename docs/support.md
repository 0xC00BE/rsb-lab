# Tested platforms and limits

The reference deployment uses six VMware guests: a firewall, a Linux Docker host,
AD/DNS and three Windows workstations. Application services, networking, optional
VPN and coordinated recovery were checked on this setup.

| Component | Tested version |
|---|---|
| VMware | vCenter 8.0.3; ESXi 8.0.0, x86-64 |
| Docker guest | Ubuntu 24.04 LTS; Docker Engine 29.1.3; Compose 2.40.3+ds1 |
| Firewall/VPN | pfSense CE 2.9.0; OpenVPN 2.7.5 |
| Windows | Server 2019 build 17763; Windows 10 Pro build 19045 |
| VPN client | Linux OpenVPN Community 2.6.19 |

The checks covered image builds, six running PLCs, live Modbus/BACnet/DNP3 data,
Scada-LTS imports, six historian measurement groups, eight Grafana panels,
Windows domain/service readiness, allowed and blocked network paths, VPN roles
and revocation, offline startup and coordinated six-VM snapshot recovery.
Dashboard-P1 through P4 passed eight browser renders across the two FUXA roles;
their 26 bundled image assets and anonymous viewer restrictions were checked.
Source CI checks configuration, unit tests, Compose interpolation and PowerShell
syntax. The [installation checklist](acceptance.md) is the operator's readiness
check for a deployment.

## Limits

- Proxmox and other hypervisors, ARM and direct Docker Desktop deployment are
  untested. Windows and mobile VPN clients are untested.
- Individual attack outcomes depend on the guest build and configuration.
  Windows local escalation behavior has not been live-tested.
- Supply licensed OS bases and allow internet access for initial dependency
  downloads. Exercises can run offline; WAN is optional for VPN access.
- Dependency pins improve repeatability, but this is not a bit-identical offline
  archive or a complete container vulnerability/license audit.
