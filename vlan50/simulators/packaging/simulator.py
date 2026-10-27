"""
simulator.py — Packaging cell
Registers (0-based):

  addr 0  PT-601 filter diff pressure mbar
  addr 1  FT-601 flow rate L/min
  addr 2  LT-601 fill level %
  addr 3  CT-601 bottle count (DINT low word)
  addr 4  TQ-601 cap torque × 10 Nm
  addr 5  CT-602 case count

Coils (0-based):
  coil 0  Filler_Run
  coil 1  Filler_CIP_Active
  coil 2  Capper_Run
  coil 3  Conv_Z1_Run
  coil 4  Conv_Z2_Run
  coil 5  Conv_Z3_Run
  coil 6  Line_EStop
  coil 7  YV-601 reject gate
"""

import random
from sim_base import BrewerySimulator


class PackagingSimulator(BrewerySimulator):

    def init_state(self):
        self.filter_dp       = 50.0    # mbar — rises as filter loads
        self.flow_rate       = 0.0     # L/min
        self.fill_level      = 75.0    # % — beer available from BBT
        self.bottle_count    = 0
        self.case_count      = 0
        self.cap_torque      = 0.0

        self._bottles_to_case = 24
        self._bottles_this_case = 0
        self._tick = 0

    def coil_addresses(self):
        return [0, 1, 2, 3, 4, 5, 6, 7]

    def step(self) -> dict:
        self._tick += 1
        dt = self.interval
        noise = lambda s=0.05: random.gauss(0, s)

        filler_run  = self.coil_states.get(0, False)
        cip_active  = self.coil_states.get(1, False)
        capper_run  = self.coil_states.get(2, False)
        z1_run      = self.coil_states.get(3, False)
        z2_run      = self.coil_states.get(4, False)
        z3_run      = self.coil_states.get(5, False)
        estop       = self.coil_states.get(6, False)

        line_active = (filler_run and not cip_active and not estop
                       and z1_run and z2_run and z3_run)

        # Filter differential pressure: rises ~0.5 mbar/min during production
        if line_active:
            self.filter_dp += 0.008 * dt + noise(0.05)
        else:
            self.filter_dp = max(50.0, self.filter_dp - 0.001 * dt)
        self.filter_dp = self.clamp(self.filter_dp, 30.0, 500.0)

        # Flow rate: depends on filler running and BBT level
        if line_active and self.fill_level > 5:
            self.flow_rate = 12.0 + noise(0.5)
            self.fill_level = max(0, self.fill_level - 0.02 * dt)
        else:
            self.flow_rate = 0.0

        # Bottle counter: one bottle per ~3 seconds when line active
        if line_active and self._tick % max(1, int(3 / dt)) == 0:
            self.bottle_count += 1
            self._bottles_this_case += 1

            # Case complete
            if self._bottles_this_case >= self._bottles_to_case:
                self.case_count += 1
                self._bottles_this_case = 0

        # Cap torque: normal 2.5–3.5 Nm, occasional out-of-range
        if capper_run and line_active:
            if random.random() < 0.005:   # 0.5% bad cap
                self.cap_torque = random.choice([0.5, 5.5])  # too loose/tight
            else:
                self.cap_torque = 3.0 + noise(0.2)
        else:
            self.cap_torque = 0.0

        return {
            0: int(self.filter_dp),
            1: int(self.flow_rate),
            2: int(self.fill_level),
            3: self.bottle_count & 0xFFFF,   # low word
            4: self.float_to_reg(self.cap_torque, 10),
            5: self.case_count & 0xFFFF,
        }


if __name__ == "__main__":
    PackagingSimulator("sim-packaging").run()
