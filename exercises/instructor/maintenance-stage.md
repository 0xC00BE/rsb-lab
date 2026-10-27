# Jump maintenance stage — spoilers

Validation status: the fixture was installed, but its escalation behavior was
not live-tested at the project owner's request. No escalation payload was run.

This stage replaces the preview's unspecified external Windows escalation
technique. The role installer includes it on `RSB-WS03` after creating the
non-administrator `svc_engagent` account. It uses native Task Scheduler and
Windows PowerShell; no exploit binary, vulnerable kernel build or download is
required. **The escalation path has not been live-tested.** Its execution test
was explicitly excluded for this release.

`RSB-Lab-Maintenance` runs as SYSTEM and executes
`C:\ProgramData\RSB-Lab\Maintenance\health.ps1` once per minute. Its normal action
only updates `health.txt`. The engineering service account has Modify access to
that one script and Read/Execute access to the directory. It can query/run the
task but cannot edit the task definition or directory permissions.

The intended finding is the difference between the script's writer and its
executor. From the agent's low-privilege context, a learner can change the script
and wait for the next scheduled run, or request that task's execution. A harmless
identity-only proof should show SYSTEM. The instructor can then demonstrate
access to the existing administrator-restricted engineering handoff, which
continues the documented scenario. Do not change other tasks or system files.

Keep a copy of the benign script before modifying it. Restore it after any
demonstration. An administrator can restore the supplied fixture with:

```powershell
.\provisioning\windows\Install-RSBMaintenance.ps1 -Reset
```

The installer refuses unrelated tasks with the same name and refuses to silently
overwrite a changed script without `-Reset`. A full cohort reset still requires
the coordinated snapshots in the reset guide. To remove this stage entirely,
stop/unregister only `RSB-Lab-Maintenance` and remove only its dedicated
Maintenance directory after preserving any exercise evidence.
