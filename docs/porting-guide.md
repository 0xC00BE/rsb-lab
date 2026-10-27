# Porting to Proxmox or another platform

The boundary is deliberate: a platform adapter creates machines and networks;
the common provisioning configures services inside the guests. No hypervisor
API, host bridge name, VM ID, datastore or physical adapter belongs in the common
Compose files. `lab/topology.json` and the firewall policy define the behavior.

## Proxmox implementation plan

1. Create five isolated bridges, or a correctly tagged VLAN-aware bridge with
   five zone tags. Leave them disconnected from production uplinks. Provide
   separate management/build connectivity for the Docker guest if needed.
2. Create a firewall guest with WAN optional, then five zone adapters. Record
   which guest interface corresponds to `lan`, `opt1`, `opt2`, `opt3`, `opt4`.
   Assign the addresses in the topology and apply the reference policy.
3. Create an x86-64 Linux Docker guest with management plus four OT adapters.
   Discover its Linux interface names; configure `.env` from those actual names.
   Ensure the bridge and any guest firewall permit the additional macvlan MACs.
   If enabling the student VPN, its Corporate bridge must also carry additional
   client MACs. Keep the common VPN role policy and run its positive/negative
   checks; do not silently replace the student TAP profile with TUN.
4. For the full scope, create the four Windows guests and optional attack VM.
   Attach each to its one lab zone, then follow the Windows guide.
5. Run the acceptance checklist. Record Proxmox version, virtual NIC model,
   bridge/VLAN arrangement, guest OS builds, allocations, and any security
   settings required for macvlan. Include negative-path tests, not only screenshots.

This is a design plan, **not a tested Proxmox recipe**. Avoid hard-coding guessed
bridge names or claiming compatibility before testing an import/build.

## What a platform contribution should contain

Add `infrastructure/<platform>/README.md`, machine/network creation templates or
scripts, a variable example without credentials, and a dated acceptance report.
Keep OS media and secrets operator-supplied. Use the common guest tools unchanged
where possible. Explicitly describe manual steps and reset behavior.

Support one full lab per reference Docker host: fixed container names and
internal IPs are intentional. Multiple cohorts require separate isolated network
sets/guests, or a more extensive address-and-name parameterization contribution.

Do not run the entire environment in a single nested VM unless your audience
already has nested virtualization enabled and that arrangement is tested.
