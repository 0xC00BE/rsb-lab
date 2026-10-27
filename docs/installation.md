# OT core installation

Use a dedicated isolated instance. See [tested platforms and limits](support.md)
for the reference setup.

1. Create the firewall and Linux guest using [requirements](requirements.md).
   Create the five isolated zones and firewall policy in [networking](networking.md).
   Give the Linux guest separate build/management connectivity and four OT adapters.
2. Clone this repository into the Linux guest. Install Python, Git, Docker Engine
   and the Compose plugin. Inspect `ip -br link` and record the four zone adapters.
3. Run `python3 tools/lab.py init`. Edit `.env` and set all four `VLAN*_PARENT`
   variables. The generated `LAB_DATA_DIR` is an absolute path under `.local/state`;
   you may choose another dedicated private state directory. Keep `.env` private.
4. Run `python3 tools/lab.py preflight`, then `python3 tools/lab.py build`.
   This builds OpenPLC at the exact upstream commit in the lock manifest and
   builds all local images. Initial builds need internet access and may take time.
5. Run `sudo python3 tools/lab.py prepare-state`. This creates storage and local
   database/broker credentials, seeds historian/MQTT flows, generates Node-RED's
   admin password hash, and sets the Node-RED/Grafana directory owners. Run it on
   the Linux guest. It preserves existing flow and credential files.
6. Install `sudo python3 provisioning/linux/host-isolation.py --install-service`.
   Disconnect temporary upstream/build connectivity after all images are built.
   Run `python3 tools/lab.py start`. Wait for the PLC web interfaces and MariaDB
   to initialize. Run `python3 tools/lab.py programs` to upload, compile, and start
   all six ST programs. This uses the fresh OpenPLC image's initial login and
   fails if authentication or compilation fails. It also
   enables persistent automatic PLC startup after a reboot.
7. Configure applications and import projects below. Verify expected connections,
   live values and firewall paths. Run `python3 tools/lab.py check` for a read-only
   Modbus/HMI sample. Complete [acceptance.md](acceptance.md) before calling the
   installation validated.

## Application setup

Use a management client or engineering workstation with the required lab access.

| Application | Endpoint | Initialization |
|---|---|---|
| Node-RED | http://10.0.20.20:1880 | Seeded by prepare-state. Administrative access is described in optional instructor material. |
| MQTT | 10.0.20.21:1883 | User `rsb_broker`; locally generated `MQTT_PASSWORD` in `.env`. |
| InfluxDB | http://10.0.30.20:8086 | User `admin`; local `INFLUXDB_PASSWORD`; org/bucket `brewery`. Initializer runs only on empty data. |
| Grafana | http://10.0.30.30:3000 | User `admin`; local `GRAFANA_PASSWORD`. Dashboard, datasource and viewer access are provisioned. |
| FUXA SCADA | http://10.0.30.10:1881 | The image includes locked Modbus/BACnet drivers. The initializer imports the project and disables BACnet on this instance. |
| FUXA HMI | http://10.0.40.10:1881 | The initializer imports the project, including BACnet, and configures editor authentication. |
| Scada-LTS | http://10.0.40.20:8080/Scada-LTS/ | The initializer imports six Modbus sources plus native BACnet/DNP3 sources, then replaces the fresh `admin/admin` password. |
| Scoreboard | http://10.0.30.40:8088 | Read-only application; verify fresh telemetry. |

For fresh applications, create temporary host management shims and run:

```bash
sudo python3 provisioning/linux/host-shims.py
sudo python3 tools/configure_fuxa.py
sudo python3 tools/configure_scadalts.py --fresh-default-login
python3 tools/validate/live_fuxa.py
```

The initializers refuse existing projects/sources. Do not rerun them to repair a
partially completed import; inspect the application and private state first.
FUXA administrator credentials are saved under
`LAB_DATA_DIR/fuxa-hmi/private-admin.json` and `fuxa-scada/private-admin.json`;
Scada-LTS uses `LAB_DATA_DIR/scadalts/private-admin.json`. Keep these files private.
FUXA anonymous viewers can read values; project saves and live value writes require
an administrator. SCADA's FUXA BACnet device is disabled because its binding
belongs to the engineering HMI (.40.10:47809).

The default FUXA project includes only Dashboard-P1 through P4, the brewery logo and equipment
artwork. The initializer assembles verified bundled images; no external asset
download is needed. See the [visual project](../projects/fuxa/README.md) for a
manual export. The Scada-LTS exports contain six
Modbus sources/142 points plus two native protocol sources/17 points. The BACnet
point network address is empty for direct IP communication; a literal `0` would
request routed BACnet addressing. DNP3 pressure inputs use raw/10 scaling, and
analog-output status uses Scada-LTS's type 64.

MariaDB uses generated credentials. `prepare-state` creates the Tomcat datasource
configuration from those credentials. Its datasource name follows upstream
[`jdbc/scadalts`](https://github.com/SCADA-LTS/Scada-LTS/blob/develop/docker/config/context.xml).
The pinned image's active configuration is its application `META-INF/context.xml`;
that path is mounted explicitly. Fresh database creation and live point storage
were verified with the pinned MariaDB image.

With the temporary management shims present, verify all six recent historian
measurements and all eight Grafana panels through their actual query endpoints:

```bash
sudo python3 tools/validate/historian.py
```

This reads local generated credentials without displaying them. A reachable
Grafana page alone does not verify historian wiring or Node-RED compatibility.

## Stop and resume

```bash
python3 tools/lab.py status
python3 tools/lab.py stop
python3 tools/lab.py start
```

`stop` preserves data. Do not delete state to fix a failed import. Back up the
state first, inspect logs, and follow [troubleshooting](troubleshooting.md).
