"""
simulator.py — Brewhouse cell
Registers (0-based):

  addr 0  TT-301 mash temp °C × 10
  addr 1  LT-301 mash level %
  addr 2  AT-301 mash pH × 100
  addr 3  AT-302 lauter turbidity NTU
  addr 4  LT-302 lauter level %
  addr 5  TT-303 kettle temp °C × 10
  addr 6  LT-303 kettle level %
  addr 7  PT-301 kettle pressure mbar
  addr 8  TT-304 whirlpool temp °C × 10
  addr 9  TT-306 chiller wort out temp °C × 10

Coils (0-based):
  coil 0  MT-301 mash agitator
  coil 1  FV-301 mash outlet valve
  coil 2  FV-302 lauter to kettle valve
  coil 3  FV-303 lauter recirculate valve
  coil 4  FV-304 kettle steam valve
  coil 5  FV-305 kettle to whirlpool
  coil 6  FV-306 whirlpool outlet
  coil 7  FV-307 chiller outlet to fermentation
"""

import random
import time
from sim_base import BrewerySimulator


class BrewhouseSimulator(BrewerySimulator):

    def init_state(self):
        # Mash tun — filled with grist + water from raw materials
        self.mash_temp = 18.0       # heats toward 67°C setpoint
        self.mash_level = 75.0
        self.mash_ph = 5.4          # target pH for mashing
        self.mash_setpoint = 67.0
        self._mash_steam = False

        # Lauter tun
        self.lauter_level = 0.0
        self.lauter_turbidity = 800.0   # NTU — high at start, clears during vorlauf

        # Kettle
        self.kettle_temp = 18.0
        self.kettle_level = 0.0
        self.kettle_pressure = 1013.0   # mbar ambient

        # Whirlpool
        self.whirlpool_temp = 95.0
        self.whirl_timer = 0            # seconds elapsed in rest

        # Wort chiller output
        self.chiller_out_temp = 95.0    # starts hot, cools as wort flows through

        self._tick = 0
        # Pentest challenge state.  The attack must include a deliberate
        # steam OFF -> ON transition while transfer, cooling, and agitation
        # are all held OFF; this avoids false positives during normal startup.
        self._steam_seen_off = False
        self._challenge_latched = False
        self._challenge_seconds = 0.0

    def coil_addresses(self):
        return [0, 1, 2, 3, 4, 5, 6, 7]

    def step(self) -> dict:
        self._tick += 1
        dt = self.interval
        noise = lambda s=0.05: random.gauss(0, s)

        agitator  = self.coil_states.get(0, False)
        mash_out  = self.coil_states.get(1, False)
        lauter_to_kettle = self.coil_states.get(2, False)
        lauter_recirc    = self.coil_states.get(3, False)
        steam_valve      = self.coil_states.get(4, False)
        kettle_out       = self.coil_states.get(5, False)
        whirl_out        = self.coil_states.get(6, False)
        chiller_out      = self.coil_states.get(7, False)

        if not steam_valve:
            self._steam_seen_off = True
        attack_pattern = (self._steam_seen_off and steam_valve and
                          not kettle_out and not chiller_out and not agitator and
                          self._tick > 10)
        if attack_pattern and not self._challenge_latched:
            self._challenge_latched = True
            self.log.warning("PENTEST BREWHOUSE: steam/transfer/cooling manipulation detected")
        if self._challenge_latched:
            self._challenge_seconds += dt

        # --- Mash tun: heat toward setpoint when steam on ---
        if steam_valve and self.mash_temp < self.mash_setpoint:
            self.mash_temp += 0.08 * dt + noise(0.02)
        else:
            self.mash_temp += (18.0 - self.mash_temp) * 0.0008 * dt + noise(0.02)
        self.mash_temp = self.clamp(self.mash_temp, 15.0, 80.0)

        # pH drifts slightly during mash
        self.mash_ph += noise(0.002)
        self.mash_ph = self.clamp(self.mash_ph, 4.8, 5.8)

        # Transfer to lauter when mash outlet open
        if mash_out and self.mash_level > 0:
            transfer = 0.3 * dt
            self.mash_level = max(0, self.mash_level - transfer)
            self.lauter_level = min(90, self.lauter_level + transfer * 0.9)

        # --- Lauter: turbidity clears during recirculation ---
        if lauter_recirc:
            self.lauter_turbidity = max(10, self.lauter_turbidity - 5 * dt)
        elif lauter_to_kettle and self.lauter_level > 0:
            self.lauter_level = max(0, self.lauter_level - 0.2 * dt)
            self.kettle_level = min(90, self.kettle_level + 0.18 * dt)
            # Turbidity rises slightly as trub transfers
            self.lauter_turbidity = min(200, self.lauter_turbidity + 1 * dt)

        # --- Kettle: heat to boil when steam valve open ---
        if self._challenge_latched:
            # The virtual batch is trapped in the kettle.  Keep the excursion
            # bounded but above the PLC alarm thresholds even after the PLC
            # closes the steam output as a safety response.
            self.kettle_level = max(self.kettle_level, 40.0)
            self.kettle_temp = min(115.0, self.kettle_temp + 0.30 * dt + noise(0.02))
        elif steam_valve and self.kettle_level > 10:
            heat_rate = 0.06 * dt
            self.kettle_temp = min(102.0, self.kettle_temp + heat_rate + noise(0.03))
        else:
            self.kettle_temp += (18.0 - self.kettle_temp) * 0.001 * dt + noise(0.03)

        # Pressure builds with temperature above 100°C
        if self._challenge_latched and self.kettle_temp >= 100.0:
            self.kettle_pressure = 1013 + (self.kettle_temp - 100.0) * 150
        elif self.kettle_temp >= 100.0:
            self.kettle_pressure = 1013 + (self.kettle_temp - 100.0) * 50
        else:
            self.kettle_pressure = 1013.0 + noise(2)

        if kettle_out and self.kettle_level > 0:
            self.kettle_level = max(0, self.kettle_level - 0.25 * dt)
            self.whirlpool_temp = self.kettle_temp  # wort arrives at kettle temp

        # --- Whirlpool: rest timer, cools slowly ---
        if whirl_out:
            self.whirl_timer += dt
        self.whirlpool_temp += (18.0 - self.whirlpool_temp) * 0.002 * dt + noise(0.05)
        self.whirlpool_temp = self.clamp(self.whirlpool_temp, 15.0, 100.0)

        # --- Wort chiller: cools whenever the whirlpool outlet feeds it. ---
        # The final chiller outlet is a product-safety valve. Using that valve
        # as the cooling trigger created a deadlock: the PLC correctly closed
        # it above 20 C, so the simulated wort could never cool below 20 C.
        if whirl_out:
            target = 14.0
            self.chiller_out_temp += (target - self.chiller_out_temp) * 0.05 * dt
            self.chiller_out_temp += noise(0.1)
        else:
            # No flow — chiller outlet temp drifts toward whirlpool temp
            self.chiller_out_temp += (self.whirlpool_temp - self.chiller_out_temp) * 0.01 * dt

        self.chiller_out_temp = self.clamp(self.chiller_out_temp, 10.0, 100.0)

        return {
            0: self.float_to_reg(self.mash_temp, 10),
            1: int(self.mash_level),
            2: self.float_to_reg(self.mash_ph, 100),
            3: int(self.lauter_turbidity),
            4: int(self.lauter_level),
            5: self.float_to_reg(self.kettle_temp, 10),
            6: int(self.kettle_level),
            7: int(self.kettle_pressure),
            8: self.float_to_reg(self.whirlpool_temp, 10),
            9: self.float_to_reg(self.chiller_out_temp, 10),
        }


if __name__ == "__main__":
    BrewhouseSimulator("sim-brewhouse").run()
