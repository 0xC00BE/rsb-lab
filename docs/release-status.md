# v0.1.0-preview.2 status

Prepared 2026-10-26 for `0xC00BE/rsb-lab` under the MIT license for original material.

A separate VMware reference environment has been reconstructed with clean OS
bases. All application images were built, six PLC programs compiled, applications
imported, and the Windows domain/roles provisioned. See [VALIDATION.md](../VALIDATION.md)
for actual results. Offline cold startup and coordinated six-VM snapshot recovery
both passed; the test environment remains isolated from upstream networks.

## Recreated and verified

- Six brewery cells, Modbus TCP, the BACnet chiller and DNP3 boiler.
- Two FUXA projects with working drivers, private editor credentials and anonymous
  viewers that cannot save projects or write live values.
- Scada-LTS: six Modbus sources/142 points, two native protocol sources/17 points,
  seven simple process views and a private generated administrator password.
- Six-cell InfluxDB historian, provisioned Grafana dashboard, and authenticated
  Node-RED flows with a working engineering message channel.
- A fresh `rs.brew` domain, three joined workstations, training accounts/OUs/GPOs,
  inventory exercise, low-privilege engineering agent and restricted handoff.
- A dedicated pfSense reference policy, isolated virtual networks, host forwarding
  guard, and positive/negative application-path tests.
- Base-image digest pins, an OpenPLC source commit, signed Debian snapshot sources,
  and FUXA/Node-RED npm lock files. No private VM image or database backup is required.

## Remaining limits

1. Hypervisor resources, OS installation/customization and domain joins are still
   operator tasks. This is source plus guest provisioning, not a one-command appliance.
2. Only the documented x86-64 VMware combination has been exercised. Proxmox,
   Hyper-V, ARM and Docker Desktop deployment are not validated.
3. Windows media, activation and any chosen local privilege-escalation exercise
   must be supplied and validated by the operator. No vulnerable Windows image or
   third-party escalation binary is bundled.
4. The optional later 62 MB FUXA artwork project remains excluded pending embedded
   asset review. The included 14-view process project is self-contained. A missing
   private Scada-LTS background reference was removed; its live values remain.
5. Image/dependency pins improve repeatability, but upstream OpenPLC installation
   still retrieves vendor-controlled build inputs. This is not a claim of fully
   bit-identical builds or an offline dependency archive.
6. GitHub-hosted CI and publication require the owner's GitHub connection. Local
   checks do not imply that a hosted workflow has run.

## Public release boundary

Only allowlisted source and newly authored configuration/tools/docs are included.
The original workspace history, vCenter connection details, private administrator
passwords, VPN profiles/keys, packet captures, database/VM backups, conversation
archives, compiled agent binaries and uncertain artwork bundles remain excluded.

Private runtime state belongs below ignored `.local/` or outside the checkout.
The release packager archives committed Git source only. Snapshots and generated
operator credentials stay on the operator's infrastructure.
