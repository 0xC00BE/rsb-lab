# Fresh deployment acceptance

The reference results are in [VALIDATION.md](../VALIDATION.md). For another build, record platform, date,
OS builds, image digests, operator, commands/results and any deviations in your
own report. Do not include `.env`, credentials, private keys or packet captures
containing unrelated traffic in a public report.

| Area | Required evidence |
|---|---|
| Build | All custom images build from this tree; OpenPLC full commit matches the lock. |
| Startup | All containers start after a clean host reboot; protocol health checks settle healthy. |
| PLCs | All six ST programs compile and report Running; all six return meaningful Modbus values. |
| HMI | FUXA imports, correct tag scaling and changing readings; Scada-LTS imports eight sources/159 points. |
| Historian | Fresh records for six cells in InfluxDB; Grafana panels update. |
| BACnet | Directed unicast read works from HMI/engineering; DMZ cannot reach it. |
| DNP3 | All nine native boiler points update from Scada-LTS; engineering can connect and DMZ cannot. |
| Corporate isolation | Arbitrary Corporate host cannot reach Node-RED, HMI or Scada-LTS directly; designated WS01 can. |
| Scoreboard | Corporate client can view .30.40:8088; board returns fresh readings and distinguishes stale/unavailable data. |
| Negative routes | Node-RED cannot initiate connections to Corporate; direct student-to-field traffic is blocked; no host-routing or IPv6 bypass. |
| Firewall | No inherited floating/group/NAT/WAN rule bypasses policy; negative tests run after clearing stale states. |
| AD, full scope | DC DNS works; workstation domain logins and intended OU memberships/GPOs apply. |
| Initial foothold | Inventory service runs as non-admin; missing name remains unresolved; intended isolated name-resolution exercise works. |
| MQTT pivot | Authenticated Node-RED job reaches agent; result shows low-privilege service context. |
| Engineering | WS03 reaches WS02 on permitted services; restricted handoff is unreadable to the low-privilege agent. |
| FUXA access | Anonymous viewer can view SCADA but cannot save projects or write live values. |
| Recovery | Process reset is documented accurately; coordinated snapshot restore returns the full exercise to its baseline. |
| Containment | No lab service is exposed on upstream/WAN or reachable from an unrelated physical LAN. |

`python3 tools/lab.py check` is a useful read-only subset, not a substitute for
this table. Complete a fresh installation on a second machine before promoting
the preview to a stable release.
