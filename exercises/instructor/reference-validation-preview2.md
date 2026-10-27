# Historical detailed validation — spoilers

# VMware reference validation

Date: 2026-10-26. Scope: a separate six-VM lab reconstructed from the sanitized
source and clean OS bases. The original lab machines and network configuration
were not used as configuration donors. The new workstations are independent full
clones; the original clean OS templates remained powered off and unchanged.

## Tested combination

- vCenter Server 8.0.3 build 24262322; ESXi 8.0.0 build 20513097.
- Ubuntu 24.04.5, Docker Engine 29.1.3, Compose 2.40.3+ds1; Docker VM 6 vCPU,
  12 GiB RAM and 120 GiB virtual disk. These are tested allocations, not minimums.
- pfSense CE 2.9.0 on a fresh 16 GiB disk with five isolated lab interfaces.
- Windows Server 2019 Standard Evaluation build 17763 and three Windows 10 Pro
  build 19045 workstations, with operator-supplied OS bases/licensing.
- Pinned application references in `lab/upstreams.lock.json`; all custom image
  builds completed, including locked FUXA drivers and the locked Node-RED tree.

## Results

| Check | Result |
|---|---|
| Source checks | Passed Python/JSON/YAML parsing, release boundary patterns, Compose references, IP uniqueness, public account consistency, Node-RED wires and documentation links. |
| Unit checks | 15 passed: six configuration, three scoreboard and six fermentation detector tests. |
| Image builds | All custom images built. OpenPLC's obsolete live Debian mirror was replaced with signed, dated snapshots. |
| PLCs | Six source programs compiled and ran. All six returned meaningful Modbus values. Persistent automatic-start settings enabled. |
| FUXA | Both 14-view projects imported. All six PLC connections and the HMI BACnet connection reported connect-ok with live values. Administrator login worked; anonymous project saves and live-value writes were rejected. |
| Scada-LTS | Eight sources, 159 points and seven simple views imported. Fresh database creation succeeded. All eight BACnet and nine DNP3 points stored values; pressure scaling and DNP3 analog-output type corrected. Default administrator password replaced and fresh login verified. |
| Historian | Recent records observed for all six measurements; all eight Grafana panels returned fresh query data. Signed dew-point conversion corrected in the flow. |
| Engineering channel | Authenticated Node-RED inject reached WS03. A read-only identity/ACL job ran as svc_engagent, without Administrators membership, and was denied access to the engineering handoff. |
| Windows domain | All three domain joins, intended OU placement and enabled GPOs verified. Each member secure channel passed. All Windows firewall profiles enabled. |
| Windows services | Inventory service running as a non-administrator; LLMNR/NetBIOS exercise settings verified. Engineering agent running under its separate low-privilege account. Jump/engineering RDP listeners present after reboot. |
| Network paths | Representative container and workstation positive/negative tests passed. Arbitrary Corporate client blocked from admin applications while designated WS01 could connect. DMZ direct field access blocked. Temporary test address removed. |
| Host bypass | Explicit attempt to route Node-RED traffic through the multi-network Docker host was rejected; temporary route removed. |
| DNP3 command/scoring | Select/operate shutdown commands reached the boiler, latched reason 303/evidence bits, and produced the live achievement indicator. Both permissives restored; corrected validation client exited successfully. |
| Process reset | All three challenge indicators returned to NOT ACHIEVED with live telemetry after reset-process. PLC commands and Windows/domain state are deliberately retained by this reset. |
| Offline cold startup | Passed after clean shutdown of all six guests. All 21 containers, six PLCs, 17 native protocol points, dashboards, message channel and member secure channels recovered without upstream connectivity. |
| Coordinated snapshot recovery | Passed: all six powered-off baselines restored together. A post-snapshot test file disappeared. Containers, six PLCs, 17 native points, fresh historian/panel data, engineering channel and Windows domain/services recovered. Inventory service uses delayed automatic startup. |
| Containment | New isolated virtual switch has no physical uplinks. Docker build adapter and firewall WAN disconnected, including connect-at-power-on settings. Temporary credential ISO detached and removed. Temporary firewall SSH access and its key removed; SSH remained disabled after restore. |
| Original resources | Repeated inventory audits found existing switches/port groups and outside VM configurations unchanged. |

## Practical limits

This validates the stated reference build and representative paths, not every
possible firewall flow or every assessed attack-chain outcome. Fermentation
confirmation/boundary/stale-read behavior has unit coverage; a complete live
Windows privilege-escalation chain and every process-attack variation were not
certified. Supply a student brief separately because instructor source/solutions
and training passwords are public.

Proxmox and other platforms are not tested. Initial builds require internet
access; exercises run with upstream adapters disconnected. No claim is made of a
complete image vulnerability/license audit or bit-identical future upstream builds.
The GitHub workflow has not run until publication and a successful hosted run.

Private credentials, management addresses, inventory IDs and raw packet captures
are not part of this report or the public source archive.
