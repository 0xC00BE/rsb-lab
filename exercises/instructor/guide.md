# Instructor reference — public preview

The intended chain is WS01 name-resolution exposure → local inventory account →
readable domain-user clue → AD deployment share → authenticated Node-RED editor →
MQTT engineering job → low-privilege WS03 service context → maintenance stage →
engineering handoff → WS02 → process protocols.

See [Windows installation](../../docs/windows.md) for provisioning and
[training accounts](../../lab/public-training-accounts.json) for
the new public example accounts. A matching public WS01 inventory example is
`Password1!`. The broker and infrastructure secrets are generated per installation.
The public engineer is `RS\henrik.solberg`; later private accounts are not used.

The WS03 agent accepts `{"job":"exec","cmd":"whoami"}` on
`rsb/eng/ws03/cmd` and publishes results on `rsb/eng/ws03/result`. Validate the
service context and restricted handoff ACLs before assigning the exercise. A
reproducible maintenance stage is included using native Windows components; see
the [maintenance-stage reference](maintenance-stage.md). That escalation path
was not live-tested at the owner's request.

## Process evidence

The source code and PLC register comments are the authoritative maps. The status
server performs reads, not process commands. Fermentation and Utilities use
HR900–HR908 evidence blocks; stale/unavailable reads are not successes.

- Fermentation: after normal cooling has been observed, sustained valid reads
  showing FV-01 glycol disabled and CO2 vent closed above **21.0 C** are required
  for five confirmation samples. An unknown read cancels confirmation. Normal
  control-band cycling around 20.5 C must not score.
- Utilities: the PLC burner-demand fix is included so steam generation has a
  working baseline. Use the documented DNP3 controls and confirm the source's
  bounded-loss conditions/evidence, not merely a momentary low pressure.
- Brewhouse: validate the kettle excursion behavior and board interpretation
  against the included simulator and PLC. It has different scoring semantics
  from the two explicit evidence-block challenges.

Complete the acceptance checklist and record safe reset steps for your platform.
Resetting simulator state alone retains PLC commands and does not restore a
compromised Windows domain. Restore coordinated clean snapshots for a new cohort.

## Optional technical references

- [Detailed Windows provisioning and scenario mechanisms](installation-reference.md)
- [Exercise security details](security-details.md)
- [Instructor acceptance and live command tests](acceptance.md)

These references contain spoilers. The normal installation guides use role
installers and readiness checks without explaining the intended solution path.
