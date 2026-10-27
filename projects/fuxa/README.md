# Complete brewery visual project

The default project contains 26 views: six black-background equipment pages,
six factory pages, seven process-flow pages and seven original value/overview
pages. It includes the brewery logo and all equipment, pipe and valve artwork.

`project.json` stores the native configuration with deduplicated asset references.
`assets-manifest.json` records the 47 bundled images, hashes and reference counts.
The artwork is distributed under MIT with the owner's permission. No external
image download or original private directory is needed.

The application initializer assembles the complete project automatically. To
produce a self-contained native file for manual import:

```bash
python3 tools/fuxa_project.py --output .local/exports/rsb-complete.fuxap
```

The earlier compact 14-view export remains in `process.fuxap` for comparison.
Use the assembled export for the finished visual experience. The two application
roles retain separate local administrator credentials. BACnet is enabled on the
engineering HMI and disabled on the Operations viewer's copied device binding.
