"""
simulator.py — Conditioning / lagering cell
Modbus registers for BBT tanks + BAC0 BACnet server for glycol chiller.

Modbus registers (0-based):
  BBT-1: addr 0–3    BBT-2: addr 10–13
  Per tank:
    +0  TT-50x temp °C × 10
    +1  PT-50x CO2 pressure mbar
    +2  LT-50x level %
    +3  AT-50x turbidity NTU

BACnet chiller (device 5001) objects:
  AI:1  glycol supply temp
  AI:2  glycol return temp
  AI:3  glycol flow rate
  BI:1  chiller run status
  BI:2  fault alarm
  AO:1  temp setpoint (writable — attack target)
  BO:1  chiller on/off (writable — attack target)
  BO:2  pump on/off (writable — attack target)

Coils (0-based):
  coil 0   FV-501 BBT-1 glycol valve
  coil 1   FV-502 BBT-1 CO2 dose
  coil 2   FV-503 BBT-1 outlet
  coil 3   FV-504 BBT-1 vent
  coil 10  FV-511 BBT-2 glycol valve
  coil 11  FV-512 BBT-2 CO2 dose
  coil 12  FV-513 BBT-2 outlet
  coil 13  FV-514 BBT-2 vent
"""

import os
import random
from bacnet_server import start_bacnet
import time
import logging
from sim_base import BrewerySimulator

log = logging.getLogger("sim-conditioning")

TEMP_SETPOINT   = 1.0     # °C — cold conditioning
CO2_SETPOINT    = 2000    # mbar — carbonation target
CO2_VENT_LIMIT  = 2500    # mbar

# ---------------------------------------------------------------------------
# BACnet chiller server (runs in a background thread)
# ---------------------------------------------------------------------------



# ---------------------------------------------------------------------------
# Main simulator
# ---------------------------------------------------------------------------

class ConditioningSimulator(BrewerySimulator):

    def init_state(self):
        self.tanks = [
            {"temp": 4.0, "pressure": 1500.0, "level": 85.0, "turbidity": 50.0},
            {"temp": 4.0, "pressure": 1200.0, "level": 70.0, "turbidity": 80.0},
        ]

        # Shared state between main loop and BACnet thread
        self.glycol_supply_temp = [TEMP_SETPOINT - 1.0]  # mutable list for threading
        self.chiller_setpoint   = [TEMP_SETPOINT]
        self.chiller_running    = [True]
        self.chiller_fault      = [False]

        device_id = int(os.environ.get("BACNET_DEVICE_ID", 5001))
        self.chiller_pump = [True]
        self.bacnet = start_bacnet(self, device_id)

    def coil_addresses(self):
        return [0, 1, 2, 3, 10, 11, 12, 13]

    def step(self) -> dict:
        dt = self.interval
        noise = lambda s=0.05: random.gauss(0, s)
        regs = {}

        chiller_ok = self.chiller_running[0] and not self.chiller_fault[0]
        setpoint   = self.chiller_setpoint[0]

        # Glycol supply temp tracks chiller setpoint
        if chiller_ok:
            target_supply = setpoint - 1.0
        else:
            target_supply = 18.0   # chiller off — glycol warms up
        self.glycol_supply_temp[0] += (
            target_supply - self.glycol_supply_temp[0]) * 0.02 * dt

        coil_map = [(0,1,2,3), (10,11,12,13)]

        for i, tank in enumerate(self.tanks):
            c = coil_map[i]
            glycol_open = self.coil_states.get(c[0], False)
            co2_dose    = self.coil_states.get(c[1], False)
            outlet_open = self.coil_states.get(c[2], False)
            vent_open   = self.coil_states.get(c[3], False)

            # Temperature: glycol cooling vs ambient leak
            if glycol_open and chiller_ok and self.chiller_pump[0]:
                tank["temp"] += (
                    self.glycol_supply_temp[0] - tank["temp"]) * 0.03 * dt
            else:
                tank["temp"] += (18.0 - tank["temp"]) * 0.002 * dt
            tank["temp"] = self.clamp(tank["temp"] + noise(0.02), -2.0, 20.0)

            # CO2 carbonation pressure
            if co2_dose and tank["pressure"] < CO2_SETPOINT:
                tank["pressure"] = min(CO2_SETPOINT + 50,
                                       tank["pressure"] + 20 * dt + noise(2))
            if vent_open or tank["pressure"] > CO2_VENT_LIMIT:
                tank["pressure"] = max(1013, tank["pressure"] - 100 * dt)
            tank["pressure"] = self.clamp(tank["pressure"] + noise(3), 1000, 3000)

            # Turbidity clears slowly during cold conditioning
            tank["turbidity"] = max(1.0, tank["turbidity"] - 0.02 * dt + noise(0.1))

            # Level drops when outlet open
            if outlet_open:
                tank["level"] = max(0, tank["level"] - 0.1 * dt)

            base = i * 10
            regs[base]     = self.float_to_reg(tank["temp"], 10)
            regs[base + 1] = int(tank["pressure"])
            regs[base + 2] = int(tank["level"])
            regs[base + 3] = int(tank["turbidity"])

        return regs


if __name__ == "__main__":
    ConditioningSimulator("sim-conditioning").run()
