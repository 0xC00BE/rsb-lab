# Installation checklist

Record platform, date, OS builds, image references and deviations in a private
operator report. Keep credentials, keys and raw captures out of public reports.

| Area | Required evidence |
|---|---|
| Build | All images build from the supplied source and lock manifest. |
| Startup | Every service returns after a clean reboot. |
| PLCs | Six programs compile, start automatically and provide changing values. |
| Visual project | Only Dashboard-P1 through P4 load with images, navigation and live values on both roles. |
| SCADA | Eight sources and 159 points import; required points update. |
| Historian | Six measurement groups and all eight Grafana panels have fresh data. |
| Domain | AD/DNS ready; three members join, receive policy and pass secure-channel checks. |
| Windows roles | Each installer completes; configured services start after reboot. |
| Network policy | Declared paths work; undeclared paths and host-routing bypasses fail. |
| Viewer permissions | Viewing works; unauthenticated configuration changes fail. |
| Optional VPN | Both roles connect from WAN; admin management works; student management and upstream access fail; revocation works. |
| Recovery | Documented process restart and coordinated six-VM recovery return the baseline. |
| Containment | WAN exposes only configured VPN listeners, without direct application access. |

Useful read-only Docker guest checks, with temporary management shims:

```bash
python3 tools/lab.py check
python3 tools/validate/live_fuxa.py
sudo python3 tools/validate/historian.py
```

On Windows use `Test-ComputerSecureChannel`, inspect role services and verify
firewall profiles after domain policy settles. Allow delayed automatic services
to start before declaring a failed installation.

See [tested platforms and limits](support.md) for the reference setup. Optional
[exercise preparation](../exercises/instructor/guide.md#instructor-preparation)
contains spoilers.
