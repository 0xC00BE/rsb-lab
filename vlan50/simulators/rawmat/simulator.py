"""
simulator.py — Raw Materials cell
Registers (0-based address = Modbus 40001 - 1):

  addr 0  LT-101 silo 1 weight kg        (raw int)
  addr 1  LT-102 silo 2 weight kg        (raw int)
  addr 2  ST-101 mill speed RPM          (raw int)
  addr 3  ZT-101 auger current A × 10
  addr 4  TT-201 HLT temp °C × 10
  addr 5  LT-201 HLT level %             (raw int)
  addr 6  FT-201 HLT outlet flow L/min   (raw int)
  addr 7  TT-202 CLT temp °C × 10
  addr 8  LT-202 CLT level %             (raw int)

Coils read back (0-based):
  coil 0  MT-101 mill motor
  coil 1  MT-102 auger motor
  coil 2  TE-201 HLT heater
  coil 3  FV-201 HLT outlet valve
  coil 4  FV-202 CLT outlet valve
"""

import math
import random
from sim_base import BrewerySimulator


class RawMaterialsSimulator(BrewerySimulator):

    def init_state(self):
        # Grain silos — start 80% full (8000 kg max each)
        self.silo1_kg = 8000.0
        self.silo2_kg = 7500.0
        self.mill_rpm = 0.0

        # HLT — starts at ambient, heater will bring it up
        self.hlt_temp = 18.0
        self.hlt_level = 90.0       # percent
        self.hlt_setpoint = 78.0

        # CLT — glycol cooled, starts near setpoint
        self.clt_temp = 4.0
        self.clt_level = 85.0
        self.clt_setpoint = 2.0

        # Small noise seeds
        self._tick = 0

    def coil_addresses(self):
        return [0, 1, 2, 3, 4]

    def step(self) -> dict:
        self._tick += 1
        dt = self.interval           # seconds per tick
        noise = lambda s=0.1: random.gauss(0, s)

        mill_on   = self.coil_states.get(0, False)
        auger_on  = self.coil_states.get(1, False)
        heater_on = self.coil_states.get(2, False)
        hlt_valve = self.coil_states.get(3, False)
        clt_valve = self.coil_states.get(4, False)

        # --- Grain silos: drain slowly when mill running ---
        if mill_on and auger_on:
            drain_rate = 0.5 * dt       # kg/s
            active_silo = 1 if self.silo1_kg > self.silo2_kg else 2
            if active_silo == 1:
                self.silo1_kg = max(0, self.silo1_kg - drain_rate)
            else:
                self.silo2_kg = max(0, self.silo2_kg - drain_rate)
            self.mill_rpm = self.clamp(1450 + noise(20), 1300, 1500)
        else:
            self.mill_rpm = 0.0

        # Auger current: normal ~4A, jam spike ~12A (rare random event)
        if auger_on:
            auger_current = 4.0 + noise(0.3)
            if random.random() < 0.002:  # 0.2% chance of jam spike
                auger_current = 12.0
        else:
            auger_current = 0.0

        # --- HLT temperature: first-order lag toward setpoint ---
        if heater_on and self.hlt_temp < self.hlt_setpoint:
            heating_rate = 0.05 * dt    # °C/s
            self.hlt_temp = min(self.hlt_setpoint + 0.5,
                                self.hlt_temp + heating_rate + noise(0.02))
        else:
            # Cool toward ambient slowly
            self.hlt_temp += (18.0 - self.hlt_temp) * 0.001 * dt + noise(0.02)

        # HLT level drains when outlet valve open
        if hlt_valve:
            self.hlt_level = max(0, self.hlt_level - 0.02 * dt)
        hlt_flow = 12.0 + noise(0.5) if hlt_valve else 0.0

        # --- CLT temperature: cooled by glycol, rises slowly if not ---
        # CLT doesn't have a heater — it's passively insulated
        self.clt_temp += (18.0 - self.clt_temp) * 0.0005 * dt    # ambient leak
        self.clt_temp += (self.clt_setpoint - self.clt_temp) * 0.01 * dt
        self.clt_temp += noise(0.02)
        self.clt_temp = self.clamp(self.clt_temp, 0.0, 20.0)

        if clt_valve:
            self.clt_level = max(0, self.clt_level - 0.015 * dt)

        return {
            0: int(self.silo1_kg),
            1: int(self.silo2_kg),
            2: int(self.mill_rpm),
            3: self.float_to_reg(auger_current, 10),
            4: self.float_to_reg(self.hlt_temp, 10),
            5: int(self.hlt_level),
            6: int(hlt_flow),
            7: self.float_to_reg(self.clt_temp, 10),
            8: int(self.clt_level),
        }


if __name__ == "__main__":
    RawMaterialsSimulator("sim-rawmat").run()
