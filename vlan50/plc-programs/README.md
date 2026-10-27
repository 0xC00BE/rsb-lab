# Brewery PLC programs

These IEC 61131-3 Structured Text programs match the register and coil maps in
the six Python process simulators. Addresses in comments are zero-based Modbus
addresses.

OpenPLC maps Modbus holding-register offsets 0-1023 to located words `%QW0`
through `%QW1023`. Located memory words `%MW0` begin at Modbus offset 1024, so
the simulator-fed process inputs intentionally use `%QW` even though the PLC
program treats them as read-only sensor values.

The programs expose alarm/status bits as additional coils so FUXA and
Scada-LTS do not need to duplicate every safety expression:

| Cell | Alarm/status coils |
|---|---|
| Raw Materials | 8 silo low, 9 auger jam, 10 HLT high, 11 tank low |
| Brewhouse | 8 turbidity, 9 kettle temp, 10 kettle pressure, 11 chiller temp, 12 whirlpool ready |
| Fermentation | 50 high pressure, 51 emergency, 52-55 tank complete |
| Conditioning | 20-23 temperature/pressure alarms, 24-25 tank ready |
| Packaging | 8 low flow, 9 cap torque, 10 filter DP, 11 source level |
| Utilities | 8 boiler trip, 9 air low, 10 CO2 low, 11 UV fault, 12 steam low, 13 water quality |

Utilities boiler telemetry is available at holding-register offsets 700-705
(Modbus 40701-40706). The Utilities simulator encodes the negative air dew
point as a signed 16-bit register.
