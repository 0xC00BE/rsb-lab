# RSB Brewery ICS Lab v0.1.0-preview.2

A source release for building an isolated industrial cybersecurity lab, backed
by a separate VMware reference reconstruction.

Includes six running OpenPLC/process cells; Modbus, BACnet and DNP3; two FUXA
projects with private editor credentials; Scada-LTS exports with eight sources
and 159 points; six-cell historian and eight Grafana panels; a Windows domain,
three workstation roles, inventory exercise and low-privilege engineering agent.

Fresh-build fixes cover image/dependency locking, legacy OpenPLC package sources,
persistent PLC startup, application initialization, Windows clone customization,
training password compatibility and network containment. Operational validators
check live values, private/anonymous access, allowed/blocked paths, the message
channel, native commands/scoring and recovery behavior. Read VALIDATION.md for
actual results and limits.

Original work is MIT licensed. OS media, VM disks, private administrator secrets,
VPN material, database backups, conversation exports and compiled tools are excluded.

**Prerelease:** hypervisor/OS provisioning remains operator supplied. Proxmox and
other platforms are community porting targets and are not tested here. The optional
later artwork-heavy FUXA project and a guaranteed Windows privilege-escalation
exploit are not included. This is not a bit-identical offline dependency archive.

Start with README.md, docs/installation.md, docs/windows.md and docs/vmware.md.
The prepared ZIP has a SHA-256 checksum; GitHub also provides source archives for
the release tag. GitHub-hosted CI must succeed after publication before its status
can be reported as passed.
