# Requirements

Use an x86-64 Linux Docker guest. The pinned DNP3 wheel targets Linux CPython
3.10; ARM and Apple Silicon builds have not been validated. A Linux VM inside
a desktop hypervisor is the intended desktop approach. Direct Docker Desktop
deployment is unsupported because the reference networking uses macvlan.

- Git, Python 3.10 or later, Docker Engine, Docker Compose plugin 2.33.1 or later
  (`gw_priority` is used), and root access for guest network/storage preparation.
- Four Linux adapters or VLAN subinterfaces connected to isolated zones 20/30/40/50.
- A dedicated firewall with five lab interfaces, one per zone; optional separate WAN.
- Internet access on the Docker guest management interface to build/pull dependencies.
- Windows Server installation media and domain-join-capable Windows workstation media,
  obtained and licensed by the operator, for the full lab.

Planning estimates, **not measured minimums**:

| Guest | Suggested initial allocation |
|---|---|
| Firewall | 2 vCPU, 2 GB RAM, 16 GB disk |
| Docker host | 4–8 vCPU, 8–12 GB RAM, 120 GB disk |
| AD/DNS | 2 vCPU, 4 GB RAM, 60 GB disk |
| Each of three workstations | 2 vCPU, 4 GB RAM, 60 GB disk |

Allow extra capacity for the hypervisor, build caches, snapshots, logs, and an
attack VM. Approximately 32 GB host RAM is a reasonable full-lab planning target;
actual consumption and available disk space still need measurement.

The reference build used Ubuntu 24.04.5, Docker Engine 29.1.3, Compose
2.40.3+ds1, pfSense CE 2.9.0, Windows Server 2019 and Windows 10 Pro. These
identify the tested combination; Windows and hypervisor software are not bundled.
