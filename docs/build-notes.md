# Findings from the first clean VMware build

These findings are reflected in the dated [validation report](../VALIDATION.md).

## OpenPLC legacy Debian package sources

The pinned OpenPLC commit uses `debian:bullseye-20240722`. Its install script
fetches build dependencies from the live Bullseye security mirror. During the
clean build, multiple referenced package files returned HTTP 404. Debian 11's
regular LTS period ended on 2026-08-31; relying on that moving mirror is unsuitable
for this source release.

The build helper now pins the base-image digest and generates a separate build
recipe pointing at Debian's **20260831T000000Z** main and security snapshots.
It retains apt package-signature verification. Disabling the date-validity check
is scoped to those dated snapshot sources. The original upstream checkout is
kept clean. This is a legacy, isolated training runtime, not a supported OS baseline.

The image built successfully and all six PLC programs compiled and returned live
Modbus data. Upstream defaults to stopped after reboot; the deployment helper now
enables the persistent `Start_run_mode` setting.

References: [Debian Bullseye LTS](https://wiki.debian.org/LTS/Bullseye),
[Debian snapshot archive](https://snapshot.debian.org/).

## Temporary build connectivity

`lab.py build` now pulls all pinned runtime images before compiling local images.
This allows the temporary build adapter to be disconnected before starting the
exercise environment. A successful `compose build` alone does not cache images
for services that have no build context.

For cloud-init-based VMware deployments, supply the actual build-interface mapping
in metadata before package installation. Configuring it only in `runcmd` is too
late for the package-installation stage. Verify package installation before marking
the bootstrap ready; do not treat the presence of a final unconditional marker as
proof of successful provisioning.

## Application initialization

- FUXA's pinned base lacked Modbus/BACnet drivers. The derived image installs
  locked drivers in a separate module directory. Fresh project import and private
  editor credentials are initialized without copying a private settings database.
- Scada-LTS's application `META-INF/context.xml` overrides the global Tomcat
  context. Mounting the generated datasource at the active path fixed fresh DB
  initialization. Native exports now include all 17 protocol points.
- A BACnet point network address of `0` requested routed addressing. An empty
  network address is required for the reference direct-IP connection. DNP3 analog
  output uses type 64, and pressure inputs need raw/10 conversion.
- The Node-RED broker's original ID equaled its node type, creating a self
  dependency in the current runtime. A distinct ID fixes startup. The broker
  credential key follows that ID. Signed dew-point decoding is explicit.
- Node-RED and FUXA npm dependency trees are locked. The locked Node-RED image was
  rebuilt and started successfully; no automatic dependency audit fixes were applied.
- A Scada-LTS background referenced a private `uploads/1.png` absent from the
  source export. That optional background was cleared; all simple value components
  remain portable.

## Windows first-build behavior

The reference clean Windows 10 clones required removal of two specific per-user
Store packages before Sysprep could complete. The clone-only repair helper uses
the error log; a Sysprep process exit code of zero alone did not indicate success.

Other fixes include first-time OU lookup, the local-user description length limit,
policy-aware power settings and supported adapter power-management commands.
Service training passwords avoid account display-name tokens rejected by Windows
complexity checks. Private administrator passwords remain unique per guest.
