"""
sim_base.py — shared base class for all brewery cell simulators.

Each simulator subclasses BrewerySimulator and implements:
  - init_state()   → set up initial process values
  - step()         → advance physics by one interval, return register dict
  - read_coils()   → list of coil addresses to read back from PLC

The base class handles:
  - Modbus TCP connection with retry
  - Writing holding registers (sensor values → PLC inputs)
  - Reading coils (PLC outputs → simulator feedback)
  - Scaling (floats stored as int × factor in Modbus registers)
  - Graceful shutdown
"""

import os
import time
import logging
import signal
import sys
from typing import Optional
from pymodbus.client import ModbusTcpClient
from pymodbus.exceptions import ModbusException

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S"
)


class BrewerySimulator:
    def __init__(self, name: str):
        self.name = name
        self.log = logging.getLogger(name)
        self.host = os.environ.get("PLC_HOST", "plc")
        self.port = int(os.environ.get("PLC_PORT", 502))
        self.interval = float(os.environ.get("SIM_INTERVAL", 2))
        self.client = None
        self.running = True
        self.coil_states = {}
        # True only when the corresponding coil was read successfully during
        # the current scan.  A failed read must never be interpreted as an
        # OFF command by process or challenge logic.
        self.coil_read_valid = {}

        signal.signal(signal.SIGTERM, self._shutdown)
        signal.signal(signal.SIGINT, self._shutdown)

        self.init_state()

    def init_state(self):
        """Override in subclass to initialise process state variables."""
        pass

    def step(self) -> dict:
        """
        Override in subclass. Advance physics by one interval.
        Returns dict of {register_address: int_value}
        Register addresses are 0-based (pymodbus convention).
        Holding registers map: address 0 = Modbus 40001.
        """
        raise NotImplementedError

    def coil_addresses(self) -> list:
        """
        Override in subclass. Return list of coil addresses to read.
        Coil addresses are 0-based (pymodbus convention).
        Coil 0 = Modbus coil 00001.
        """
        return []

    # -------------------------------------------------------------------------
    # Helpers
    # -------------------------------------------------------------------------

    def float_to_reg(self, value: float, scale: int = 10) -> int:
        """Scale float to int for Modbus register storage."""
        return max(0, min(65535, int(round(value * scale))))

    def clamp(self, value, lo, hi):
        return max(lo, min(hi, value))

    def read_coil(self, address: int) -> Optional[bool]:
        """Read one coil, returning None when its state is unknown."""
        if not self.client or not self.client.is_socket_open():
            return None
        try:
            result = self.client.read_coils(address, count=1, slave=1)
            if result.isError():
                return None
            return result.bits[0]
        except Exception:
            return None

    def write_registers(self, reg_dict: dict):
        """Write multiple holding registers. reg_dict: {address: int_value}"""
        if not self.client or not self.client.is_socket_open():
            return
        for address, value in sorted(reg_dict.items()):
            try:
                self.client.write_register(address, int(value), slave=1)
            except Exception as e:
                self.log.warning(f"Write failed reg {address}: {e}")

    # -------------------------------------------------------------------------
    # Connection management
    # -------------------------------------------------------------------------

    def connect(self):
        self.log.info(f"Connecting to PLC at {self.host}:{self.port}")
        while self.running:
            try:
                self.client = ModbusTcpClient(self.host, port=self.port)
                if self.client.connect():
                    self.log.info("Connected to PLC")
                    return
            except Exception as e:
                self.log.warning(f"Connection failed: {e} — retrying in 5s")
            time.sleep(5)

    def ensure_connected(self):
        if not self.client or not self.client.is_socket_open():
            self.connect()

    # -------------------------------------------------------------------------
    # Main loop
    # -------------------------------------------------------------------------

    def run(self):
        self.connect()
        self.log.info(f"Simulator running — interval {self.interval}s")
        while self.running:
            try:
                self.ensure_connected()

                # Read coil feedback from PLC before stepping physics
                for addr in self.coil_addresses():
                    value = self.read_coil(addr)
                    self.coil_read_valid[addr] = value is not None
                    if value is not None:
                        # Preserve the last known-good state if a later read
                        # fails.  Consumers can inspect coil_read_valid when
                        # they require fresh evidence from this scan.
                        self.coil_states[addr] = value

                # Advance physics and write sensor values
                registers = self.step()
                self.write_registers(registers)

                self.log.debug(f"Wrote {len(registers)} registers")
            except ModbusException as e:
                self.log.warning(f"Modbus error: {e}")
                self.client = None
            except Exception as e:
                self.log.error(f"Unexpected error: {e}")

            time.sleep(self.interval)

        self.log.info("Simulator stopped")
        if self.client:
            self.client.close()

    def _shutdown(self, *_):
        self.log.info("Shutdown signal received")
        self.running = False
