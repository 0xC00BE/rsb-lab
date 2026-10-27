# Reset and backup

`python3 tools/lab.py reset-process` restarts the brewhouse, fermentation and
utilities simulators. Their in-memory latches and process state reset. PLC
commands remain in memory, so an attack still commanded by a PLC can trigger
again. Return relevant commands to baseline and verify scoreboard telemetry.
This is **not** a complete exercise reset.

For a full reset, prepare a clean validated baseline, shut down all lab guests,
and take a coordinated snapshot/backup of the firewall, Docker guest, DC and
workstations. Restore them together on the same isolated topology. Avoid restoring
only the domain controller while keeping arbitrary later member-machine state.
Do not distribute snapshots containing private administration credentials.

If VPN access is enabled, keep WAN disconnected during a cohort restore.
Firewall snapshots also restore certificate and revocation records. Preserve
current private records and reapply later revocations, or issue a new cohort PKI,
before reopening WAN. A restored older snapshot does not retain later revocations.

Before changing applications, save native project exports and database-native
backups. Copying an actively written database directory is not a consistent
database backup. With all services cleanly stopped, back up the entire local
state directory plus `.env`, firewall configuration and platform network mapping.
Store these private backups outside the public repository. Test restoration.

`stop` preserves persistent state. The supplied tools never recursively delete
your data directory. Start a separate new state directory for a disposable clean
build rather than destroying an existing installation to troubleshoot it.
