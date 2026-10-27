# Optional remote access

Remote access is optional. The offline lab runs with WAN disconnected. When
enabled, the dedicated pfSense WAN may use DHCP on the operator's upstream
network. Reserve its lease or update the client endpoint if the address changes.
An upstream router may need VPN-only port forwards for internet clients; that
router configuration is separate from this project.

The configuration has two independent roles, with separate certificate authorities:

| Role | Intended access |
|---|---|
| Administrator | TUN, UDP 1194, `10.254.10.0/24`: management and all five internal lab zones. |
| Student | TAP, UDP 1195, `10.0.10.160â€“190`: Corporate exercise access, local discovery and the status board. Corporate machines can contact the client; Jump callbacks use TCP 22/80/443/3389. No firewall management, direct OT application access or upstream forwarding. |

Each person receives a unique client certificate and private profile. Profiles
are generated locally, never distributed in the source release. Keep private
keys, the certificate authority and firewall backups outside Git. Revoking a
client must stop that identity from reconnecting without affecting other users.

Only the VPN listeners should be allowed on WAN. Do not publish FUXA, RDP, SSH,
database, Docker or pfSense web management directly through WAN. Keep the Docker
guest's temporary build adapter disconnected when remote access is enabled.

## Install on the dedicated firewall

Use pfSense CE **2.9.x** with the reference five-zone policy already installed.
The adapter expects `lan`, `opt1`â€¦`opt4` at the documented gateways and unused
`opt5`/`opt6` slots. It refuses existing VPNs, bridges, WAN pass rules, floating
rules, port forwards or UPnP. Take a private configuration backup and recovery
snapshot first. This initializer is for a dedicated lab firewall.

For student TAP, enable promiscuous mode, MAC changes and forged transmits only
on the new Corporate port group. The other lab port groups retain their macvlan
settings. Keep the isolated switch without physical uplinks.

Copy `provisioning/firewall/vpn.php` and a private copy of
`vpn-settings.example.json` to the firewall through your trusted management
channel. Set `endpoint` to a client-reachable hostname/address. Set
`allow_private_wan_clients` to `true` only when clients reach WAN through a
private upstream network. That removes WAN's private-source block after the
dedicated-policy checks; it does not add a general WAN allow rule.

From the firewall's local root shell, preview and apply:

```sh
php /root/vpn.php initialize /root/vpn-settings.private.json
php /root/vpn.php initialize /root/vpn-settings.private.json --apply
```

It creates the Corporate/TAP bridge, member filtering and only the two VPN WAN
listeners. Scoped egress connection states support the approved callbacks across
bridge members. It disables automatic web-management anti-lockout; administrators
use their admin profile. Default deny rules cover IPv4 and IPv6.

Run initialization once. It refuses to replace an existing VPN installation. If
interrupted, inspect and restore the saved configuration or snapshot before
retrying; deleting its private directory alone does not roll back the changes.

## Administrator and student profile versions

On each Windows lab guest, run the optional host adapter elevated, selecting its
role (`AD`, `Corporate`, `Jump` or `Engineering`):

```powershell
.\provisioning\windows\Configure-RSBVpnAccess.ps1 -Role Corporate
```

It enables RDP/WinRM and limits the added management rules to `10.254.10.0/24`.
The AD role also permits domain administration protocols from that pool. For a
new build, `Install-RSBRole.ps1 -Role Corporate -EnableVpn` applies it as part of
role setup. Windows firewall profiles remain enabled.

Issue a different lowercase identifier to each person:

```sh
php /root/vpn.php issue admin operator
php /root/vpn.php issue student student01
```

Retrieve `/conf/rsb-vpn/rsb-admin-operator.ovpn` and
`/conf/rsb-vpn/rsb-student-student01.ovpn` privately. Give each person only their
own file. Each contains a private client key; do not put profiles in Git, release
assets, shared VM templates or screenshots. Files are owner-readable only. Back
up `/conf/rsb-vpn/` and the firewall configuration privately. Client certificates
expire after 365 days. Both roles use TLS 1.2+, encrypted control channels and
AEAD data ciphers.

## Connect

Use **OpenVPN Community 2.6+ with TAP support** for students on a dedicated Linux
or Windows exercise machine. On Windows, install TAP-Windows6 and select
`windows-driver tap-windows6` in the local profile if necessary. OpenVPN Connect
does not support this TAP profile; see its
[official FAQ](https://openvpn.net/connect-docs/windows-faq/). The administrator
profile uses TUN, without Ethernet bridging.

On Linux:

```sh
chmod 600 rsb-student-student01.ovpn
sudo openvpn --config rsb-student-student01.ovpn
```

Wait for `Initialization Sequence Completed`. Use the TAP adapter's address as
the student Corporate address. Preserve its stable MAC setting when reconnecting.
Use one connection per identity; issue another identity for another machine.
Avoid client networks overlapping the lab subnets. The status board is at
`http://10.0.30.40:8088`.

Plain Linux OpenVPN requires resolver integration to apply pushed DNS settings;
use the distribution's OpenVPN integration, with DNS `10.0.10.2` for `rs.brew`.
See the [OpenVPN manual](https://openvpn.net/community-docs/community-articles/openvpn-2-6-manual/)
for driver and DNS behavior. This is split tunnel: ordinary internet access
continues through the participant's own connection.

The student client participates in Corporate discovery and accepts approved
exercise callbacks. Use a dedicated exercise machine and allow only the
listeners needed for the session in that machine's firewall.

## Refresh or revoke

Re-export an existing valid identity without replacing its certificate:

```sh
php /root/vpn.php export student student01
```

Revoke an identity:

```sh
php /root/vpn.php revoke student student01
```

Revocation updates the role's revocation list and restarts that role's listener.
Other clients of that role may take about a minute to reconnect. The other role
is independent. A revoked identity cannot be exported again; keep its record and
issue a new identifier for replacement access. If the endpoint changes, update
the `remote` line in private profiles. Export uses the endpoint stored in
`/conf/rsb-vpn/state.json`.

## Client support

See [tested platforms and limits](support.md) for verified server/client versions.

Exercise-specific access rationale is in the optional
[instructor guide](../exercises/instructor/guide.md), which contains spoilers.
