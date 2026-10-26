PROGRAM plc_prg
VAR
    AirPressure       AT %QW0 : INT;
    AirDewPoint       AT %QW1 : INT;
    CO2Pressure       AT %QW2 : INT;
    CO2Level          AT %QW3 : INT;
    Conductivity      AT %QW4 : INT;
    UVLampOK          AT %QW5 : INT;

    BoilerDrumPress   AT %QW700 : INT;
    SteamHeaderPress  AT %QW701 : INT;
    FlueTemp          AT %QW702 : INT;
    FeedWaterLevel    AT %QW703 : INT;
    BurnerStatus      AT %QW704 : INT;
    ReliefStatus      AT %QW705 : INT;

    BurnerEnable      AT %QX0.0 : BOOL;
    FeedPump          AT %QX0.1 : BOOL;
    AirHeaderValve    AT %QX0.2 : BOOL;
    CO2Regulator      AT %QX0.3 : BOOL;
    WaterOutlet       AT %QX0.4 : BOOL;

    AlarmBoilerTrip   AT %QX1.0 : BOOL; (* coil 8 *)
    AlarmAirLow       AT %QX1.1 : BOOL; (* coil 9 *)
    AlarmCO2Low       AT %QX1.2 : BOOL; (* coil 10 *)
    AlarmUVFault      AT %QX1.3 : BOOL; (* coil 11 *)
    AlarmSteamLow     AT %QX1.4 : BOOL; (* coil 12 *)
    AlarmWaterQuality AT %QX1.5 : BOOL; (* coil 13 *)
END_VAR

AlarmBoilerTrip := (BoilerDrumPress > 100) OR (FeedWaterLevel < 10);
AlarmSteamLow := SteamHeaderPress < 40;
AlarmAirLow := AirPressure < 50;
AlarmCO2Low := CO2Level < 20;
AlarmUVFault := UVLampOK = 0;
AlarmWaterQuality := Conductivity > 100;

(* Boiler burner demand control.
   Drum pressure register is bar x 10, so 70 = 7.0 bar setpoint.
   Hysteresis band 6.6-7.0 bar lets the burner cycle and hold steam
   pressure instead of staying off from cold start. *)
IF BoilerDrumPress < 66 THEN
    BurnerEnable := TRUE;
ELSIF BoilerDrumPress >= 70 THEN
    BurnerEnable := FALSE;
END_IF;

(* Safety trip always overrides burner demand. *)
IF AlarmBoilerTrip THEN
    BurnerEnable := FALSE;
END_IF;

(* Feed-water level control with hysteresis, kept well above the
   10% low-level trip so the burner interlock stays satisfied. *)
IF FeedWaterLevel < 40 THEN
    FeedPump := TRUE;
ELSIF FeedWaterLevel >= 70 THEN
    FeedPump := FALSE;
END_IF;

IF AlarmCO2Low THEN
    CO2Regulator := FALSE;
END_IF;

IF AlarmUVFault OR AlarmWaterQuality THEN
    WaterOutlet := FALSE;
END_IF;

END_PROGRAM

CONFIGURATION Config0
    RESOURCE Res0 ON PLC
        TASK task0(INTERVAL := T#100ms, PRIORITY := 0);
        PROGRAM instance0 WITH task0 : plc_prg;
    END_RESOURCE
END_CONFIGURATION
