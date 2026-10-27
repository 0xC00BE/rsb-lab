# Brewery dashboards

The project contains **Dashboard-P1, Dashboard-P2, Dashboard-P3 and Dashboard-P4**.
P1 is the start page; navigation lists the four dashboards in order.

`project.json` stores native configuration with deduplicated asset references.
`assets-manifest.json` records the 26 PNG assets, hashes and reference counts.
Artwork is MIT licensed with the owner's permission and requires no external
image downloads. The [brewery logo](assets/8a8b99411a0cc214a32a.png) also serves
as the repository logo and a reusable project icon.

The application initializer assembles the project automatically. For a native
file suitable for manual import:

```bash
python3 tools/fuxa_project.py --output .local/exports/rsb.fuxap
```

To apply this bundled project to an initialized installation, use temporary
management shims and review the operation before applying:

```bash
python3 tools/update_fuxa.py
python3 tools/update_fuxa.py --apply
```

The updater backs up the project in its private state directory and preserves
editor credentials. Unknown custom views or device IDs stop the operation for
review. BACnet is enabled on the engineering HMI and disabled on the Operations
viewer's copied binding. See the [gallery](../../docs/gallery.md) for the screens.
