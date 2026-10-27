# Network contract

The public address inventory is [lab/topology.json](../lab/topology.json).
Keep these internal subnets for the first build. Changing them requires changing
Compose, flows, dashboards, PLC targets, Windows scripts, and firewall policy.
Historical private notes disagree about WS01; this release consistently uses
**10.0.10.3**. It does not assert the original running machine currently uses it.

| Zone | Subnet | Gateway | pfSense logical interface | Docker guest setting |
|---|---|---|---|---|
| Corporate | 10.0.10.0/24 | 10.0.10.1 | lan | No Docker adapter needed |
| DMZ | 10.0.20.0/24 | 10.0.20.1 | opt1 | VLAN20_PARENT |
| Operations | 10.0.30.0/24 | 10.0.30.1 | opt2 | VLAN30_PARENT |
| Engineering | 10.0.40.0/24 | 10.0.40.1 | opt3 | VLAN40_PARENT |
| Field | 10.0.50.0/24 | 10.0.50.1 | opt4 | VLAN50_PARENT |

Each zone can be a separate virtual switch without physical VLAN tags. A VLAN
trunk is also possible, with matching guest VLAN subinterfaces. Do not mix tagged
and untagged configurations. The names are logical zones, not a requirement to
attach to a physical switch.

Reserve .1 for the firewall and .254 for optional management. Do not attach
physical production networks to these switches. Keep the Docker guest's upstream
management/default route separate. Do not configure the guest as the lab router.

Macvlan emits multiple container MAC addresses behind each Linux adapter. Your
virtual switch must permit them. Check MAC filtering, port security, forged
transmit, and promiscuous-mode requirements for your chosen platform; these
settings are platform-specific. The Docker host cannot normally communicate
with its own macvlan containers directly. Optional temporary host shims:

```bash
sudo python3 provisioning/linux/host-shims.py
```

This adds a .254 management interface on each Docker zone and is lost on reboot.
Inspect routing first: a host adapter already numbered on the same subnet can
create a competing route. Use a client VM in the correct zone instead if you do
not need host management. Never treat this multi-homed management guest as a
student foothold. Check that it does not provide a forwarding bypass around the firewall.

Install the host forwarding guard before enabling the exercise networks:

```bash
sudo python3 provisioning/linux/host-isolation.py --install-service
```

The service rejects forwarding through the four OT parents and their optional
management shims. The private PLC/simulator bridges continue to work. Disconnect
the temporary build adapter before handing the lab to students. Leave firewall
WAN disconnected for offline use; enable only the documented VPN listeners for
optional [remote access](vpn.md).

## Firewall

On a **dedicated new lab pfSense**, assign the logical interfaces above, set
their .1/24 addresses, disable IPv6 for the exercise, and remove broad inherited
LAN allows. Use the console to avoid losing access while adjusting rules.
Copy `provisioning/firewall/` onto that firewall, export a configuration backup,
and preview:

```sh
php apply-policy.php
# Review policy.json and the interface addresses before applying.
php apply-policy.php --apply
pfctl -nf /tmp/rules.debug
```

The script validates interface addresses, backs up config.xml, and replaces the
five lab interfaces' rules. It preserves other interface rules, so audit WAN,
floating rules, interface groups, NAT/port forwards, automatic rules, and any
VPN settings separately. Existing states may survive a policy change: clear old
lab states before negative-path tests. Do not expose lab services on WAN.

The JSON policy is the common porting contract; pfSense PHP is a reference
adapter tested on a fresh pfSense CE 2.9.0 firewall. Other firewalls can implement
the same stateful allow paths followed by per-zone default deny. Same-subnet
traffic does not traverse this firewall. Detailed exercise protocol behavior is
in the optional [instructor material](../exercises/instructor/guide.md).

Use directed BACnet unicast. Cross-zone broadcast discovery and BBMD are not
configured. Simulator private bridge networks remain internal to the Docker host.

Operational checks include `sudo python3 tools/validate/network_paths.py` and
`provisioning/windows/Test-RSBNetworkPaths.ps1`. The optional host-bypass test
temporarily creates and removes one route inside the Node-RED container.

Reference: [Docker macvlan documentation](https://docs.docker.com/engine/network/drivers/macvlan/).
