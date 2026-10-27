"""
simulator.py — Fermentation cell
Four tanks, identical physics offset by register address.

Register map (0-based), each tank block is 10 registers apart:
  Tank 1: addr 0–5    Tank 2: addr 10–15
  Tank 3: addr 20–25  Tank 4: addr 30–35

Per tank (offset 0):
  +0  TT-4xx temp °C × 10
  +1  PT-4xx pressure mbar
  +2  LT-4xx level %
  +3  AT-4xx pH × 100
  +4  PT-405 CO2 header pressure mbar  (shared, written by tank 1 only)
  +5  FT-401 CO2 flow L/min            (shared, written by tank 1 only)

Coils (0-based), each tank block 10 apart:
  +0  FVx01 glycol valve
  +1  FVx02 outlet valve
  +2  FVx03 CIP inlet
  coil 40: FV-440 CO2 vent
  coil 41: FV-441 CO2 recovery

Challenge evidence registers (0-based, common layout):
  900  tamper latch (0=normal, 1=triggered)
  901  event counter
  902  reason code (202=FV-01 glycol disabled with vent closed)
  903  seconds since event
  904  simulator boot/reset identifier
  905  glycol-disable command observed (0/1)
  906  vent-closed condition observed (0/1)
  907  event Unix timestamp, high word
  908  event Unix timestamp, low word
"""

import random
import time
from sim_base import BrewerySimulator

N_TANKS = 4
TEMP_SETPOINT = 20.0      # °C — ale fermentation
TEMP_SETPOINT_LAGER = 10.0
PRESSURE_MAX = 1500       # mbar — vent trips above this
CO2_RECOVERY_PRESS = 1200 # mbar — recovery starts
CHALLENGE_CONFIRM_SAMPLES = 5  # 10 seconds at the default 2-second interval


class FermentationSimulator(BrewerySimulator):

    def init_state(self):
        self.tanks = []
        for i in range(N_TANKS):
            self.tanks.append({
                "temp":     TEMP_SETPOINT + random.uniform(-1, 1),
                "pressure": 1013.0 + random.uniform(0, 100),
                "level":    80.0 + random.uniform(-5, 5),
                "ph":       4.8 + random.uniform(0, 0.3),
                # Fermentation progress: 0.0 = just pitched, 1.0 = complete
                "progress": random.uniform(0.1, 0.9),
            })
        self.co2_header_press = 1100.0
        self._tick = 0
        self._t1_glycol_seen_on = False
        self._challenge_condition_samples = 0
        self._challenge_latched = False
        self._challenge_seconds = 0.0
        self._challenge_event_count = 0
        self._challenge_reason = 0
        self._challenge_event_epoch = 0
        self._challenge_evidence_1 = 0
        self._challenge_evidence_2 = 0
        self._challenge_boot_id = int(time.time()) & 0xFFFF

    def coil_addresses(self):
        coils = []
        for i in range(N_TANKS):
            base = i * 10
            coils += [base, base + 1, base + 2]
        coils += [40, 41]
        return coils

    def step(self) -> dict:
        self._tick += 1
        dt = self.interval
        noise = lambda s=0.05: random.gauss(0, s)

        regs = {}

        total_co2 = 0.0

        for i, tank in enumerate(self.tanks):
            base_reg  = i * 10
            base_coil = i * 10

            glycol_open = self.coil_states.get(base_coil,     False)
            outlet_open = self.coil_states.get(base_coil + 1, False)
            cip_open    = self.coil_states.get(base_coil + 2, False)

            if i == 0:
                glycol_read_valid = self.coil_read_valid.get(base_coil, False)
                vent_read_valid = self.coil_read_valid.get(40, False)

                if glycol_read_valid and glycol_open:
                    self._t1_glycol_seen_on = True

                # Detector threshold (21.0 C) is deliberately above the PLC
                # glycol-control point (ON >20.5 C / OFF <19.5 C). Normal
                # hysteresis cycling keeps FV-01 at/below ~20.6 C, so routine
                # cooling cycles no longer race the detector and auto-trigger
                # the scenario. A sustained tamper that holds glycol off still
                # warms the tank past 21.0 C within a few minutes.
                challenge_condition = (
                    glycol_read_valid and vent_read_valid and
                    self._t1_glycol_seen_on and not glycol_open and
                    not self.coil_states.get(40, False) and
                    tank["temp"] > 21.0 and self._tick > 20
                )

                if challenge_condition and not self._challenge_latched:
                    self._challenge_condition_samples += 1
                else:
                    # Confirmation requires consecutive, successful reads.
                    # An unknown or restored state cancels the pending event.
                    self._challenge_condition_samples = 0

                if (self._challenge_condition_samples >= CHALLENGE_CONFIRM_SAMPLES and
                        not self._challenge_latched):
                    self._challenge_latched = True
                    self._challenge_event_count += 1
                    self._challenge_reason = 202
                    self._challenge_event_epoch = int(time.time())
                    self._challenge_evidence_1 = 1
                    self._challenge_evidence_2 = 1
                    self.log.warning(
                        "PENTEST FERMENTATION: FV-01 glycol disabled above "
                        "setpoint for %d consecutive valid samples",
                        self._challenge_condition_samples,
                    )
            if i == 0 and self._challenge_latched:
                self._challenge_seconds += dt

            # --- Temperature: fermentation generates heat, glycol removes it ---
            # Active fermentation adds ~0.5°C/hr heat load
            ferment_heat = 0.002 * (1.0 - tank["progress"]) * dt
            tank["temp"] += ferment_heat

            if self._challenge_latched and i == 0:
                # Deliberately bounded product-quality excursion.  The PLC may
                # command the valve back on, but the simulated actuator fault
                # keeps cooling unavailable until the lab is reset.
                tank["temp"] = min(32.0, tank["temp"] + 0.08 * dt + noise(0.02))
            elif glycol_open:
                cooling = 0.04 * dt
                tank["temp"] = max(TEMP_SETPOINT - 1.0,
                                   tank["temp"] - cooling + noise(0.02))
            else:
                tank["temp"] += (22.0 - tank["temp"]) * 0.001 * dt + noise(0.02)

            tank["temp"] = self.clamp(tank["temp"], 0.0, 35.0)

            # --- Pressure: CO2 produced by yeast during active fermentation ---
            co2_production = 8.0 * (1.0 - tank["progress"]) * dt  # mbar/tick
            if self._challenge_latched and i == 0:
                co2_production *= 2.0
            tank["pressure"] += co2_production + noise(1)

            vent_open = self.coil_states.get(40, False)
            if vent_open or tank["pressure"] > PRESSURE_MAX:
                tank["pressure"] = max(1013, tank["pressure"] - 50 * dt)

            tank["pressure"] = self.clamp(tank["pressure"], 1000, 2000)
            total_co2 += max(0, tank["pressure"] - 1013)

            # --- pH: drops during fermentation (yeast produces acids) ---
            tank["ph"] -= 0.0005 * (1.0 - tank["progress"]) * dt + noise(0.001)
            tank["ph"] = self.clamp(tank["ph"], 3.8, 5.5)

            # --- Fermentation progress: advances based on time and temp ---
            rate = 0.00005 * dt
            if abs(tank["temp"] - TEMP_SETPOINT) < 2.0:
                rate *= 1.5   # optimal temp accelerates fermentation
            tank["progress"] = min(1.0, tank["progress"] + rate)

            # Level: drops slightly as CO2 is produced and outlet opens
            if outlet_open:
                tank["level"] = max(0, tank["level"] - 0.1 * dt)

            regs[base_reg]     = self.float_to_reg(tank["temp"], 10)
            regs[base_reg + 1] = int(tank["pressure"])
            regs[base_reg + 2] = int(tank["level"])
            regs[base_reg + 3] = self.float_to_reg(tank["ph"], 100)

        # CO2 header — aggregate of all tanks
        self.co2_header_press = self.clamp(
            1013 + total_co2 / N_TANKS + noise(5), 1000, 2000
        )
        co2_flow = max(0, (self.co2_header_press - 1013) * 0.02 + noise(0.5))

        regs[4]  = int(self.co2_header_press)
        regs[5]  = int(co2_flow)

        # Authoritative challenge evidence. Process measurements remain useful
        # context, but only this exact-sequence latch is used for scoring.
        regs[900] = 1 if self._challenge_latched else 0
        regs[901] = self._challenge_event_count
        regs[902] = self._challenge_reason
        regs[903] = min(65535, int(self._challenge_seconds))
        regs[904] = self._challenge_boot_id
        regs[905] = self._challenge_evidence_1
        regs[906] = self._challenge_evidence_2
        regs[907] = (self._challenge_event_epoch >> 16) & 0xFFFF
        regs[908] = self._challenge_event_epoch & 0xFFFF

        return regs


if __name__ == "__main__":
    FermentationSimulator("sim-fermentation").run()
