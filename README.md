# RSB Brewery ICS Lab

A segmented industrial cybersecurity training lab: six brewery process cells,
OpenPLC controllers, Modbus TCP, BACnet/IP, DNP3, FUXA, Scada-LTS, a historian,
and an optional Windows domain attack path.

**v0.1.0-preview.2 — VMware reference build.** The OT services and Windows domain
have been reconstructed in a separate isolated VMware lab from this source,
with clean OS bases. See the dated [validation report](VALIDATION.md) for the
checks completed and remaining limits. Hypervisor provisioning and OS media are
operator supplied; Proxmox deployment is not yet tested. Read the
[release status](docs/release-status.md) before building.

## What is included

- Six IEC 61131-3 Structured Text programs and Python process simulators.
- Four configurable Docker Compose stacks for the OT services.
- BACnet chiller and DNP3 boiler implementations and health checks.
- Native FUXA process views, eight-source/159-point Scada-LTS exports, Grafana dashboard,
  and repaired Node-RED historian flows with an engineering MQTT channel.
- Windows domain configuration, deliberate training weaknesses, and agent source.
- A platform-neutral [topology](lab/topology.json), explicit
  [firewall policy](provisioning/firewall/policy.json), local lifecycle tools,
  reset guidance, release checks, and a [porting guide](docs/porting-guide.md).

No VM disks, Windows media, VPN profiles, private lab credentials, live database
backups, compiled engineering-agent binaries, or conversation archives are included.

## Choose a scope

| Scope | Machines you provide | Purpose |
|---|---|---|
| OT core | Dedicated lab firewall and Linux Docker VM; a client with access to the lab networks | Process simulation, dashboards, and protocol exercises |
| Full lab | OT core plus AD/DNS server, corporate workstation, DMZ jump host, engineering workstation, optional attack VM | Domain and IT/OT pivot exercises |

The current repository does not provision a hypervisor. You create the machines
and isolated networks, then use the common guest configuration. Start with
[requirements](docs/requirements.md), [installation](docs/installation.md), and
[networking](docs/networking.md). Windows setup is in [the full lab guide](docs/windows.md).
The tested VMware layout is described in [the reference build guide](docs/vmware.md).

```mermaid
flowchart LR
  IT[Corporate / VLAN 10] --- FW[Dedicated lab firewall]
  FW --- DMZ[DMZ / VLAN 20\nNode-RED · MQTT · jump host]
  FW --- OPS[Operations / VLAN 30\nFUXA · historian · Grafana · scoreboard]
  FW --- ENG[Engineering / VLAN 40\nFUXA · Scada-LTS · workstation]
  FW --- FIELD[Field / VLAN 50\nSix PLC cells · BACnet · DNP3]
```

## First steps on your Linux Docker VM

After creating the isolated networks and attaching the guest adapters:

```bash
python3 tools/lab.py init
# Edit .env: set VLAN20_PARENT through VLAN50_PARENT to your Linux interfaces.
python3 tools/lab.py preflight
python3 tools/lab.py build
sudo python3 tools/lab.py prepare-state
python3 tools/lab.py start
python3 tools/lab.py programs
# Create temporary management shims, import projects, and configure authentication
# as described in docs/installation.md. Drivers are included in the image build.
python3 tools/lab.py check
```

Run Docker commands with the account/privileges required by your host. The
initial image build requires internet access; the exercise runs offline after staging.
Do not start this on the original live host: fixed container names and lab
addresses intentionally identify a separate instance.

## Training credentials and scope

All accounts in [public-training-accounts.json](lab/public-training-accounts.json)
are new public examples. Database, broker, and dashboard secrets are generated
locally by `init` and kept out of Git. Instructor solutions are public in this
repository; distribute student briefs separately for an assessed exercise.
See [SECURITY.md](SECURITY.md) and [reset instructions](docs/reset.md).

## Contributing and license

Proxmox, VMware, Hyper-V, and other platform adapters are welcome. Report what
you actually tested using the [acceptance checklist](docs/acceptance.md).
See [CONTRIBUTING.md](CONTRIBUTING.md). Original project material is MIT licensed;
external software retains its own terms: [third-party notices](THIRD_PARTY_NOTICES.md).
