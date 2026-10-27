# RSB Brewery ICS Lab v0.1.0

A complete source release for an isolated industrial cybersecurity lab, verified
through an independent six-VM VMware build from repository files and clean OS bases.

The release includes six OpenPLC/process cells; Modbus TCP, BACnet/IP and DNP3;
the complete **26-view FUXA project and all 47 artwork assets** on both visual roles;
Scada-LTS exports with eight sources and 159 points; six-cell historian and eight
Grafana panels; and a Windows domain with three workstation roles and supporting
service source. A VMware adapter creates independent OS clones, isolated networks
and bounded resources, and stages guest customization.

Optional pfSense VPN configuration provides separate administrator and student
identities. Administrator access covers lab management; the student profile joins
the Corporate exercise network. Keys and client profiles are generated privately
for each installation. See [the VPN guide](docs/vpn.md).

Installation guides avoid solution details. The [student brief](exercises/student/brief.md)
and optional, clearly labelled [instructor material](exercises/instructor/guide.md)
are separate. The added Jump-host exercise extension was installed, but its
escalation behavior was excluded from live testing. No escalation payload was run.

Validation covered image builds, PLC compilation/startup, all 52 FUXA view renders,
viewer restrictions, native protocol samples, historian panels, domain/service
readiness, allowed/blocked paths, VPN roles and revocation, offline cold startup,
and coordinated six-VM recovery. See [the dated report](VALIDATION.md) for scope.

Original code, documentation and the authorized FUXA artwork are MIT licensed.
Supply your own OS media/licensing and infrastructure. VM disks, private
administrator credentials, VPN keys/profiles and database backups are excluded.
Proxmox and other platforms are porting targets and are not validated here.
Dependency pins improve repeatability; this is not a bit-identical offline archive
or a complete image vulnerability/license audit.

Start with [README.md](README.md). The release includes a committed-source ZIP
and its SHA-256 checksum. Earlier prereleases remain available unchanged.
