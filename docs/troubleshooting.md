# Troubleshooting

| Symptom | Check |
|---|---|
| Preflight rejects a placeholder | Run init, then fill in all four Linux parent interfaces in .env. |
| Compose rejects gw_priority | Use Compose plugin 2.33.1 or later. |
| Docker host cannot ping its containers | Expected macvlan host isolation. Use an appropriate client or the optional host shim. |
| Container unreachable through virtual switch | Check guest adapter/zone mapping and allowance for multiple container MAC addresses. |
| Permission denied writing Node-RED or Grafana state | Run prepare-state elevated on Linux; verify state filesystem supports Unix ownership. |
| Node-RED fails reading admin.hash | Build its custom image before prepare-state, then check the generated state file and uid 1000 ownership. |
| Grafana shows no data | Check Node-RED module installation, flow errors, InfluxDB v2 token/org/bucket, timestamps and .20.20 to .30.20:8086 routing. |
| Scada-LTS fails startup | Inspect Tomcat and MariaDB logs; verify the generated jdbc/scadalts datasource and exact image's context handling. This combination needs fresh-build validation. |
| PLC compilation fails | Inspect deployment-helper output and upstream OpenPLC build logs. A running container does not mean its PLC program is running. |
| BACnet device offline on SCADA | Disable its copied engineering-HMI binding; this preview uses BACnet on the VLAN40 HMI. |
| Protocol container replies use wrong interface | Confirm Compose honors gw_priority for the field network; inspect route tables inside the dual-network simulator. |
| Domain join fails | Use DC DNS 10.0.10.2, correct guest clock, and verify AD service/RPC paths. |
| Scenario instantly triggers again after reset | Simulator reset leaves PLC commands intact. Return commands to baseline first. |

Avoid replacing digest pins with `latest` as a repair. Record the failing version,
reproduce the issue in a disposable copy, and contribute a tested pin update.
