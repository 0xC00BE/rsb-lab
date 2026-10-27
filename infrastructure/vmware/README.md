# VMware machine provider

This adapter creates six independent OS clones, a new folder/resource pool and
five new port groups on an uplink-free standard switch. It does not adopt or
replace existing resources. The shared guest installers remain the same for
other hypervisors. An independent six-VM source build verified this adapter and the shared guest
configuration. See the [reference build guide](../../docs/vmware.md) and
[validation scope](../../docs/support.md).

## Inputs

Prepare powered-off, generalizable OS templates: pfSense CE 2.9, Ubuntu 24.04,
Windows Server 2019 and Windows 10. Obtain media/licensing separately. Templates
must contain only OS preparation tools, with no lab application state or VPN
material. Prefer generalized, workgroup-only Windows bases. A legacy clone must
successfully generalize into WORKGROUP before joining the new lab domain.
Remove inherited auto-login settings and disable unused template accounts on the
new clones with the documented finalization step before exercises.
The provider never edits a source template. It clones every disk independently.

The tested Ubuntu OVA is pinned to its dated official build and SHA256 in
`lab/os-media.lock.json`. Download it with `python tools/download_os_media.py`;
import it as a powered-off clean template before its first boot. Its
[official build index](https://cloud-images.ubuntu.com/noble/20261017/) and
[checksums](https://cloud-images.ubuntu.com/noble/20261017/SHA256SUMS) remain available
independently of this repository. OS media is excluded from source release assets.

Copy `spec.example.json` to ignored `.local/vmware/spec.private.json`, then set
the actual vCenter, target host, datastore, existing parent folder/resource pool,
upstream port group and template names. Give the instance, VM prefix, switch and
port groups unused names. Keep the specification and deployment state private.

For a vCenter with a private certificate, export and verify its leaf certificate
through your trusted administrator channel and set `vcenter_certificate` to that
local PEM file. The provider trusts that leaf for TLS discovery and connections;
an incorrect certificate is rejected before authentication. With `null`, it uses
normal system CA/hostname validation. It does not offer an insecure TLS switch.

Install `requirements.txt` in a Python 3.11+ virtual environment. Supply
`VCENTER_USER`/`VCENTER_PASSWORD` privately through the process environment, or
use the interactive prompts. Do not put a password in the specification, command
line, Git or a shared shell transcript.

## Plan, create and inspect

From the repository root:

```sh
python infrastructure/vmware/provider.py plan --spec .local/vmware/spec.private.json
python infrastructure/vmware/provider.py create --spec .local/vmware/spec.private.json
python infrastructure/vmware/provider.py status --spec .local/vmware/spec.private.json
```

The default state file is `.local/vmware/deployment.json`. Keep it: its inventory
IDs and ownership token limit later operations to this instance. A different
deployment needs a different specification, state path and unused resource names.

All six clones remain powered off initially. Upstream adapters are disconnected
and do not connect at boot. The new lab port groups permit the MAC behavior
needed by OT macvlan and the optional Corporate student VPN. No existing network
security setting is changed. The Docker disk grows to at least 120 GiB; grow its
guest filesystem when initializing the OS.

## Faster guest preparation

The companion adapter stages Windows customization and Ubuntu cloud-init through
vCenter, without operating the user's screen:

```sh
python infrastructure/vmware/customize.py windows --spec .local/vmware/spec.private.json
python infrastructure/vmware/customize.py linux --spec .local/vmware/spec.private.json
```

It generates `.local/vmware/deployment.guests.private.json` with a different
private administrator password per guest. Protect that file. The Ubuntu seed
installs OS/Docker tools, names adapters by MAC and temporarily connects only its
build adapter. It does not start exercise applications. An optional
`--ssh-public-key` gives the operator key-based Linux access.

Prepare private firewall media, optionally with a temporary provisioning key:

```sh
python infrastructure/vmware/firewall_media.py create --spec .local/vmware/spec.private.json --ssh-public-key OPERATOR-PUBLIC-KEY.pub --upload
python infrastructure/vmware/customize.py start --role Firewall --spec .local/vmware/spec.private.json
```

The ISO contains a private administrator setting; never publish it. In the new
firewall's local shell, mount its optical device read-only and run:

```sh
mkdir -p /mnt/rsb-bootstrap
mount_cd9660 -o ro /dev/cd0 /mnt/rsb-bootstrap
php /mnt/rsb-bootstrap/bootstrap.php
php /mnt/rsb-bootstrap/bootstrap.php --apply
umount /mnt/rsb-bootstrap
```

The dry run verifies six NIC MACs before any change. Applying assigns the five
zones, DHCP WAN, base policy and private administrator. The optional preparation
channel is key-only, bound to `10.0.20.1:2222`, and allowed only from the Linux
management shim `10.0.20.254`; it does not enable system SSH or WAN management.
Its host-key fingerprint is printed for out-of-band verification. It is
nonpersistent: after a reboot an operator must explicitly start it again with
`/usr/sbin/sshd -f /conf/rsb-platform/provisioning-sshd.conf` if still needed.

Cleanly power off that firewall, then remove its private media:

```sh
python infrastructure/vmware/firewall_media.py cleanup --spec .local/vmware/spec.private.json
```

This removes only the recorded temporary optical device and ISO in the owned
VM's datastore folder. Delete the local private ISO after completing preparation.
Start the firewall again before domain/application setup. For each other role,
use `customize.py start --role Docker` (or `AD`, `Corporate`, `Jump`, `Engineering`)
with the same specification. Wait for AD/DNS before domain joins.

Verify Ubuntu's `cloud-init status --wait` and `/var/lib/rsb-bootstrap-ready`.
Then `customize.py clear-seed --spec ...` clears VMware seed credential copies.
Follow the [common installation](../../docs/installation.md) for actual brewery
configuration. Before starting exercises, install the forwarding guard and use
`customize.py disconnect-build --spec ...` to disconnect the build adapter.
Use the [Windows guide](../../docs/windows.md), including clone-only Sysprep
repair when required, member joins, role installation and finalization.

After VPN/application preparation, run
`php /conf/rsb-platform/finalize-provisioning.php` on the firewall to remove the
temporary rule, authorized key and daemon. The base-policy refresh preserves
installed VPN role rules. Finish with the [acceptance checklist](../../docs/acceptance.md).
The provider's `create` result means **OS clones ready**, not an installed brewery.

## Interrupted creation

With a saved state, rerunning `create` verifies the existing-resource baseline
and recorded VM ownership, then resumes missing clones. It refuses changed
specifications and unrecorded VM names. An interruption during initial network
creation requires inspection of the recorded instance resources; it does not
automatically adopt partial resources. Preserve state and inspect the vCenter
task before retrying a timed-out clone. There is no automatic destructive cleanup.
