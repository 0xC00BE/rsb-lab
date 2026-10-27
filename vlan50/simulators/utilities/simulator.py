"""
simulator.py — Utilities cell
Modbus registers (0-based):

  addr 0  PT-711 air receiver pressure bar × 10
  addr 1  AT-711 air dew point °C × 10
  addr 2  PT-721 CO2 tank pressure bar × 10
  addr 3  LT-721 CO2 tank level %
  addr 4  AT-731 water conductivity µS/cm
  addr 5  XT-731 UV lamp status (1=ok, 0=fault)

  addr 700  PT-701 steam drum pressure bar x 10 (Modbus 40701)
  addr 701  PT-702 steam header pressure bar x 10
  addr 702  TT-701 flue gas temp C
  addr 703  LT-701 feed water level %
  addr 704  Burner run status (1=run)
  addr 705  Relief valve status (1=open)

Boiler values served via DNP3 outstation (pydnp3):
  AI:0  PT-701 steam drum pressure bar × 10
  AI:1  PT-702 steam header pressure bar × 10
  AI:2  TT-701 flue gas temp °C
  AI:3  LT-701 feed water level %
  BI:0  burner run status
  BI:1  relief valve open
  AO:0  pressure setpoint (writable — attack target)
  BO:0  burner enable (writable — attack target)
  BO:1  feed pump run (writable — attack target)

Coils (Modbus, 0-based):
  coil 0  FV-701 burner enable
  coil 1  MT-701 feed pump
  coil 2  FV-711 air header valve
  coil 3  FV-721 CO2 regulator
  coil 4  FV-731 water outlet

Challenge evidence registers (0-based, common layout):
  900  tamper latch (0=normal, 1=triggered)
  901  event counter
  902  reason code (303=DNP3 burner and feed-pump shutdown)
  903  seconds since event
  904  simulator boot/reset identifier
  905  DNP3 burner-off command observed (0/1)
  906  DNP3 feed-pump-off command observed (0/1)
  907  event Unix timestamp, high word
  908  event Unix timestamp, low word
"""

import os
import random
from dnp3_server import BoilerOutstation
import time
import logging
from sim_base import BrewerySimulator

log = logging.getLogger("sim-utilities")

BOILER_SETPOINT_DEFAULT = 7.0   # bar
BOILER_MAX_PRESSURE     = 10.0  # bar — hardwired trip


# ---------------------------------------------------------------------------
# DNP3 outstation (background thread using pydnp3)
# ---------------------------------------------------------------------------



# ---------------------------------------------------------------------------
# Main simulator
# ---------------------------------------------------------------------------

class UtilitiesSimulator(BrewerySimulator):

    def init_state(self):
        # Boiler state
        self.boiler = {
            "drum_press":   5.0,    # bar — warms up to setpoint
            "header_press": 4.8,
            "flue_temp":    120.0,  # °C
            "fw_level":     75.0,   # %
            "burner_run":   False,
            "relief_open":  False,
            "setpoint":     BOILER_SETPOINT_DEFAULT,
        }

        # Compressed air
        self.air_press  = 7.0    # bar
        self.air_dewpt  = -20.0  # °C — well dried

        # CO2 bulk tank
        self.co2_press  = 60.0   # bar — liquid CO2 storage
        self.co2_level  = 80.0   # %

        # Water treatment
        self.conductivity = 45.0  # µS/cm — RO permeate
        self.uv_ok        = True
        self._uv_fault_tick = 0

        # Shared state dict for DNP3 thread
        self.dnp3_state = dict(self.boiler)

        # Commands are permissives: remote enable cannot bypass PLC interlocks.
        self.dnp3 = BoilerOutstation()
        self._healthy_ticks = 0
        self._challenge_latched = False
        self._challenge_seconds = 0.0
        self._challenge_event_count = 0
        self._challenge_reason = 0
        self._challenge_event_epoch = 0
        self._challenge_evidence_1 = 0
        self._challenge_evidence_2 = 0
        self._challenge_boot_id = int(time.time()) & 0xFFFF

    def coil_addresses(self):
        return [0, 1, 2, 3, 4]

    def step(self) -> dict:
        dt = self.interval
        noise = lambda s=0.05: random.gauss(0, s)

        command = self.dnp3.commands()
        self.boiler['setpoint'] = command['setpoint']
        burner_enable = self.coil_states.get(0, True) and command['burner_enable']
        pump_run      = self.coil_states.get(1, True) and command['pump_enable']
        air_valve     = self.coil_states.get(2, True)
        co2_valve     = self.coil_states.get(3, True)
        water_valve   = self.coil_states.get(4, True)

        # Arm from the requested DNP3 permissives as well as the effective PLC
        # outputs.  The PLC may keep its burner output off at idle, but the
        # challenge still needs a healthy command period before accepting a
        # deliberate two-command shutdown.
        if command['burner_enable'] and command['pump_enable']:
            self._healthy_ticks += 1
        if (self._healthy_ticks > 20 and not command['burner_enable'] and
                not command['pump_enable'] and
                not self._challenge_latched):
            self._challenge_latched = True
            self._challenge_event_count += 1
            self._challenge_reason = 303
            self._challenge_event_epoch = int(time.time())
            self._challenge_evidence_1 = 1
            self._challenge_evidence_2 = 1
            self.log.warning("PENTEST UTILITIES: DNP3 burner/feed-pump shutdown detected")
        if self._challenge_latched:
            self._challenge_seconds += dt

        # --- Boiler ---
        b = self.boiler
        b["burner_run"] = burner_enable and b["fw_level"] > 10

        if b["burner_run"] and b["drum_press"] < b["setpoint"]:
            b["drum_press"] += 0.03 * dt + noise(0.005)
            b["flue_temp"]  += 0.5  * dt + noise(0.5)
        elif b["drum_press"] >= b["setpoint"]:
            b["drum_press"] += noise(0.01)   # slight fluctuation at setpoint
            b["flue_temp"]  = self.clamp(b["flue_temp"] + noise(1), 100, 350)
        else:
            decay = 0.06 if self._challenge_latched else 0.01
            b["drum_press"] = max(0, b["drum_press"] - decay * dt)
            b["flue_temp"]  = max(20, b["flue_temp"] - 1 * dt)

        b["drum_press"] = self.clamp(b["drum_press"], 0, 15)

        # Relief valve: opens above max, stays open until pressure drops
        if b["drum_press"] >= BOILER_MAX_PRESSURE:
            b["relief_open"] = True
        if b["relief_open"]:
            b["drum_press"] = max(b["setpoint"] * 0.9,
                                  b["drum_press"] - 0.1 * dt)
            if b["drum_press"] < BOILER_MAX_PRESSURE * 0.9:
                b["relief_open"] = False

        # Header pressure lags drum slightly
        b["header_press"] += (b["drum_press"] * 0.95 - b["header_press"]) * 0.1

        # Feed water level: pump fills, steam boiling consumes
        if pump_run:
            b["fw_level"] = min(100, b["fw_level"] + 0.05 * dt)
        if b["burner_run"]:
            b["fw_level"] = max(0, b["fw_level"] - 0.03 * dt)

        # Update DNP3 shared state
        self.dnp3_state.update(b)
        self.dnp3.publish(b, pump_run)

        # --- Compressed air ---
        if air_valve:
            # Demand drains receiver slightly
            self.air_press = max(5.0, self.air_press - 0.01 * dt + noise(0.02))
        else:
            self.air_press = min(8.0, self.air_press + 0.02 * dt)
        self.air_dewpt += noise(0.1)
        self.air_dewpt = self.clamp(self.air_dewpt, -40, 10)

        # --- CO2 bulk tank ---
        if co2_valve:
            self.co2_level = max(0, self.co2_level - 0.005 * dt)
        self.co2_press = self.clamp(55 + self.co2_level * 0.1 + noise(0.5),
                                    0, 80)

        # --- Water treatment ---
        self.conductivity += noise(0.5)
        self.conductivity = self.clamp(self.conductivity, 10, 200)

        # UV lamp: random fault ~1% chance per hour
        if self.uv_ok and random.random() < 0.00001 * dt:
            self.uv_ok = False
            log.warning("UV lamp fault simulated")
        # Auto-recover after 5 min (for lab reset convenience)
        if not self.uv_ok:
            self._uv_fault_tick += 1
            if self._uv_fault_tick > 300 / dt:
                self.uv_ok = True
                self._uv_fault_tick = 0
                log.info("UV lamp recovered")

        return {
            0: self.float_to_reg(self.air_press, 10),
            1: self.signed_float_to_reg(self.air_dewpt, 10),
            2: self.float_to_reg(self.co2_press, 10),
            3: int(self.co2_level),
            4: int(self.conductivity),
            5: 1 if self.uv_ok else 0,
            700: self.float_to_reg(b["drum_press"], 10),
            701: self.float_to_reg(b["header_press"], 10),
            702: int(b["flue_temp"]),
            703: int(b["fw_level"]),
            704: 1 if b["burner_run"] else 0,
            705: 1 if b["relief_open"] else 0,
            900: 1 if self._challenge_latched else 0,
            901: self._challenge_event_count,
            902: self._challenge_reason,
            903: min(65535, int(self._challenge_seconds)),
            904: self._challenge_boot_id,
            905: self._challenge_evidence_1,
            906: self._challenge_evidence_2,
            907: (self._challenge_event_epoch >> 16) & 0xFFFF,
            908: self._challenge_event_epoch & 0xFFFF,
        }


if __name__ == "__main__":
    UtilitiesSimulator("sim-utilities").run()
