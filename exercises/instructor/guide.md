# Instructor guide — spoilers

This guide describes **one possible attack path**, not a required or exhaustive
solution. Learners may find other routes through the lab. Local escalation
options depend on the installed Windows build, patches, privileges and tools.
Keep assessments open to alternative approaches within the assigned scope.

Use the [Windows guide](../../docs/windows.md) for installation and the
[installation checklist](../../docs/acceptance.md) for readiness. Public exercise
accounts are listed in [training accounts](../../lab/public-training-accounts.json).
Database, broker, VPN and administrator credentials are generated per installation;
never reuse public training accounts for management.

## Example route

WS01 name-resolution exposure → local inventory account → readable domain-user
clue → AD deployment share → authenticated Node-RED editor → MQTT job on WS03 →
local privilege escalation → engineering handoff → WS02 → process protocols.

The WS01 inventory account example is `Password1!`. The engineering identity is
`RS\henrik.solberg`. Domain group/share permissions expose the Node-RED deployment
credential; the engineering handoff is restricted to administrators.

The WS03 agent accepts `{"job":"exec","cmd":"whoami"}` on `rsb/eng/ws03/cmd`
and publishes results on `rsb/eng/ws03/result`. It runs as the non-administrator
`svc_engagent` account. Confirm that context and restricted handoff access before
assigning an assessed exercise.

## Jump-host privilege escalation

Learners can investigate local configuration weaknesses or Windows escalation
techniques appropriate to their guest. Potato-family techniques may also work
when their privilege, service and patch prerequisites are met; availability is
not guaranteed. No third-party escalation binary is bundled.

The included maintenance task is one lab-specific option. `RSB-Lab-Maintenance`
runs as SYSTEM once per minute and executes
`C:\ProgramData\RSB-Lab\Maintenance\health.ps1`. Its benign action updates
`health.txt`. The service account has Modify access to that script, Read/Execute
access to the directory and permission to query/run the task, but cannot change
the task definition or directory permissions.

The finding is the difference between who can write the script and who executes
it. A learner with the service account's context can modify the script and wait
for the scheduled run or request execution. An identity-only proof can establish
the resulting context before accessing the restricted engineering handoff.
**The fixture's installation was checked; its escalation behavior has not been
live-tested.** Verify any chosen route on your guest build before using it in an
assessment.

Preserve the benign script before a demonstration and restore it afterward.
An administrator can restore the supplied fixture with:

```powershell
.\provisioning\windows\Install-RSBMaintenance.ps1 -Reset
```

The installer rejects unrelated tasks with the same name and requires `-Reset`
before overwriting a changed script. To remove the fixture, unregister only its
named task and remove its dedicated Maintenance directory after preserving
exercise evidence.

## Process evidence

The source and PLC register comments define the process maps. The scoreboard
reads process evidence; it does not issue process commands. Fermentation and
Utilities expose HR900–HR908 evidence blocks. Stale/unavailable reads do not
establish success.

- **Brewhouse:** demonstrate the kettle excursion and check the scoreboard's
  interpretation against the simulator and PLC.
- **Fermentation:** after observing normal cooling, FV-01 glycol disabled and
  CO2 vent closed above 21.0 °C must persist for five valid confirmation samples.
  An unknown read cancels confirmation; normal cycling around 20.5 °C does not score.
- **Utilities:** use the available protocol controls and verify the bounded-loss
  conditions/evidence in the source. Momentary low pressure alone is insufficient.

## Instructor preparation

Check the inventory service's non-administrator context, the name-resolution
exercise, the MQTT agent context and handoff permissions. Choose and verify the
local escalation route for the assessed guest build. Confirm process scoring and
reset behavior without treating the example route as the only acceptable solution.

Process reset retains PLC commands and Windows/domain state. Use coordinated
clean snapshots for a new cohort, following [reset instructions](../../docs/reset.md).
Protect the locally generated, unencrypted Node-RED credential file and all other
private state through directory permissions and Docker-host administration.
