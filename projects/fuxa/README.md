# Current brewery dashboards

The default installation contains **only Dashboard-P1, Dashboard-P2,
Dashboard-P3 and Dashboard-P4**, exported from the current production HMI.
The start page is P1; the navigation contains these four dashboards in order.
The release corrects a stale start-page reference and the P4 menu spelling.

`project.json` stores native configuration with deduplicated asset references.
`assets-manifest.json` records the 26 current PNG images, hashes and reference
counts. Artwork is MIT licensed with the owner’s permission. No external image
download or original private directory is needed. The logo in these screens
is also the repository’s [logo and reusable icon](assets/8a8b99411a0cc214a32a.png).

The initializer assembles the project automatically. For a self-contained native
file for manual import:

```bash
python3 tools/fuxa_project.py --output .local/exports/rsb-current.fuxap
```

## Upgrade an existing release installation

With temporary management shims present, first review the replacement:

```bash
python3 tools/update_fuxa.py
python3 tools/update_fuxa.py --apply
```

The upgrade recognizes the earlier release dashboards, backs up each project
under its private state directory, then replaces the entire visual project.
Old views are removed rather than retained beside P1–P4. Editor credentials stay
unchanged. Unrecognized custom views or device IDs stop the upgrade for review.
`legacy-views.json` is only a migration allowlist; it contains no old dashboards.

The earlier compact `process.fuxap` export and unused legacy artwork have been
removed. BACnet stays enabled on the engineering HMI and disabled on the
Operations viewer’s copied binding. Production itself is read only during export.
