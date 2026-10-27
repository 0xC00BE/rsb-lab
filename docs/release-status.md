# v0.1.1 release status

VMware reference build verified on 2026-10-26; FUXA updated on 2026-10-27 for `0xC00BE/rsb-lab`. Original material and the authorized
FUXA artwork use MIT; third-party components retain their own terms.

An independent six-VM VMware environment was built using the repository's provider,
guest configuration and project imports. Clean OS bases supplied the operating
systems. No existing lab configuration or application database was used as a donor.
The primary release environment continues separately. See [VALIDATION.md](../VALIDATION.md)
for tested versions, evidence and limits.

## Included and verified

- Six brewery cells, persistent PLC startup, Modbus TCP, BACnet and DNP3.
- Current FUXA project: only Dashboard-P1 through P4, all 26 artwork files,
  updated navigation and production logo. See the dated validation report for
  the dashboard update checks and the earlier full VMware build.
- Scada-LTS: eight sources/159 points and stored samples for 17 native points.
- Six-cell historian, eight Grafana panels and the engineering message channel.
- A new domain, three joined workstations, role services, unique Windows identities,
  enabled host firewalls and removed template login settings.
- Separate administrator/student VPN roles, private identity generation, revocation,
  intended access and representative blocked paths. Both roles worked after reboot.
- Isolated VMware networks, bounded new resources, host forwarding protection,
  offline cold startup and coordinated six-VM snapshot recovery.
- Source checks, 19 unit tests, Windows source parsing and committed dependency pins.

## Practical limits

1. Supply OS bases, Windows licensing and infrastructure. The adapter assists
   VMware deployment; this is not a prebuilt VM appliance or a one-command OS installer.
2. The documented x86-64 VMware combination is validated. Proxmox, Hyper-V,
   ARM and Docker Desktop deployment are not validated.
3. The Jump-host extension is included and its installation was confirmed. Its
   escalation behavior is not live-tested; no external escalation binary is required.
4. Initial image/tool downloads need internet access. Application exercises run
   with the build connection disconnected; firewall WAN is optional for VPN.
5. Upstream-controlled build inputs prevent a claim of bit-identical future
   builds. A complete image vulnerability audit and third-party SBOM are outside
   this validation scope.

## Public release boundary

The release contains committed source, project exports, bundled artwork and guides.
Private deployment state, vCenter details, administrator passwords, VPN identities,
packet captures, VM/database backups, conversation archives and compiled service
binaries are excluded. Generate private state below ignored `.local/` or outside
the checkout. Operator snapshots and credentials remain on the operator's systems.
