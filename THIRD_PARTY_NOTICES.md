# Third-party components

The root MIT license applies to original lab code, configuration and documentation
made available by 0xC00BE. It does not replace upstream licenses or grant rights
to Windows media, container images or third-party binaries.

External components are retrieved during a build, rather than bundled as
executables or VM disks. Review each upstream's license and redistribution
requirements if you distribute built images or modified upstream software:

| Component | Upstream |
|---|---|
| OpenPLC v3 | https://github.com/thiagoralves/OpenPLC_v3 |
| FUXA | https://github.com/frangoteam/FUXA |
| Scada-LTS | https://github.com/SCADA-LTS/Scada-LTS |
| Node-RED | https://github.com/node-red/node-red |
| Node-RED container package metadata | https://github.com/node-red/node-red-docker |
| FUXA Modbus driver dependency | https://www.npmjs.com/package/modbus-serial |
| FUXA BACnet driver dependency | https://www.npmjs.com/package/node-bacnet |
| Node-RED Modbus nodes | https://www.npmjs.com/package/node-red-contrib-modbus |
| Node-RED InfluxDB nodes | https://www.npmjs.com/package/node-red-contrib-influxdb |
| bcryptjs | https://www.npmjs.com/package/bcryptjs |
| InfluxDB | https://github.com/influxdata/influxdb |
| Grafana | https://github.com/grafana/grafana |
| MariaDB | https://mariadb.org/about/#licensing |
| Mosquitto | https://mosquitto.org/documentation/ |
| pymodbus | https://github.com/pymodbus-dev/pymodbus |
| BACpypes3 | https://github.com/JoelBender/BACpypes3 |
| dnp3-python | https://pypi.org/project/dnp3-python/ |
| argcomplete | https://github.com/kislyuk/argcomplete |
| Python and base OS packages | https://docs.python.org/3/license.html |

Windows and pfSense are installed separately by the operator and retain their
own terms. No live VPN credentials, third-party escalation tool or qModMaster
binary is included. The complete FUXA project and its 26 current bundled artwork files
are included under MIT with the project owner's redistribution authorization
of 2026-10-26. Hashes and embedded reference counts are recorded in
`projects/fuxa/assets-manifest.json`.

Upstream image references, source commit and direct package pins are recorded in
`lab/upstreams.lock.json`. Transitive dependency licenses and complete software
bills of materials should be generated when publishing built container images;
this source release does not claim a complete image-license audit.
