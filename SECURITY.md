# Security and exercise scope

This is an intentionally vulnerable lab. Run it only on isolated virtual
networks you control. No exercise service should be exposed to a public or
organizational LAN. The firewall, hypervisor and upstream management network are
outside student attack scope.

Training features include public example passwords, weak name resolution,
readable credential clues, deliberately permissive domain memberships, an
authenticated Node-RED deployment editor, arbitrary-command MQTT agent jobs,
unauthenticated industrial protocols and anonymous Grafana viewing.

The repository's public training credentials are examples, not a secret inventory
for the original private lab. Never reuse them for management or elsewhere.
`init` generates local database, broker and dashboard credentials. The `.env`,
Node-RED credential file, state, snapshots and configuration backups remain
private and excluded from Git. Node-RED's locally generated credential file is
unencrypted by design; protect its directory and Docker-host administration.

The release scanner is a publication safeguard, not a proof that every possible
secret has been detected. Review staged files before publishing changes. Do not
attach original database dumps, VPN files or student evidence to public issues.

For an unintended security issue, use GitHub private vulnerability reporting if
the repository owner enables it. Otherwise report a minimal description without
credentials or exploit evidence in a public issue and request a private channel.
