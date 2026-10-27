PROGRAM plc_prg
VAR
    T1Temp       AT %QW0 : INT;
    T1Pressure   AT %QW1 : INT;
    T1Level      AT %QW2 : INT;
    T1PH         AT %QW3 : INT;
    CO2Header    AT %QW4 : INT;
    CO2Flow      AT %QW5 : INT;

    T2Temp       AT %QW10 : INT;
    T2Pressure   AT %QW11 : INT;
    T2Level      AT %QW12 : INT;
    T2PH         AT %QW13 : INT;
    T3Temp       AT %QW20 : INT;
    T3Pressure   AT %QW21 : INT;
    T3Level      AT %QW22 : INT;
    T3PH         AT %QW23 : INT;
    T4Temp       AT %QW30 : INT;
    T4Pressure   AT %QW31 : INT;
    T4Level      AT %QW32 : INT;
    T4PH         AT %QW33 : INT;

    T1Glycol     AT %QX0.0 : BOOL;
    T1Outlet     AT %QX0.1 : BOOL;
    T1CIP        AT %QX0.2 : BOOL;
    T2Glycol     AT %QX1.2 : BOOL;
    T2Outlet     AT %QX1.3 : BOOL;
    T2CIP        AT %QX1.4 : BOOL;
    T3Glycol     AT %QX2.4 : BOOL;
    T3Outlet     AT %QX2.5 : BOOL;
    T3CIP        AT %QX2.6 : BOOL;
    T4Glycol     AT %QX3.6 : BOOL;
    T4Outlet     AT %QX3.7 : BOOL;
    T4CIP        AT %QX4.0 : BOOL;
    CO2Vent      AT %QX5.0 : BOOL;
    CO2Recovery  AT %QX5.1 : BOOL;

    AlarmHighPressure AT %QX6.2 : BOOL; (* coil 50 *)
    AlarmEmergency    AT %QX6.3 : BOOL; (* coil 51 *)
    T1Complete        AT %QX6.4 : BOOL; (* coil 52 *)
    T2Complete        AT %QX6.5 : BOOL; (* coil 53 *)
    T3Complete        AT %QX6.6 : BOOL; (* coil 54 *)
    T4Complete        AT %QX6.7 : BOOL; (* coil 55 *)
END_VAR
VAR
    T1FermentTimer : TON;
    T2FermentTimer : TON;
    T3FermentTimer : TON;
    T4FermentTimer : TON;
END_VAR

IF T1Temp > 205 THEN T1Glycol := TRUE; ELSIF T1Temp < 195 THEN T1Glycol := FALSE; END_IF;
IF T2Temp > 205 THEN T2Glycol := TRUE; ELSIF T2Temp < 195 THEN T2Glycol := FALSE; END_IF;
IF T3Temp > 205 THEN T3Glycol := TRUE; ELSIF T3Temp < 195 THEN T3Glycol := FALSE; END_IF;
IF T4Temp > 205 THEN T4Glycol := TRUE; ELSIF T4Temp < 195 THEN T4Glycol := FALSE; END_IF;

AlarmHighPressure := (T1Pressure > 1500) OR (T2Pressure > 1500) OR
                     (T3Pressure > 1500) OR (T4Pressure > 1500);
AlarmEmergency := (T1Pressure > 2000) OR (T2Pressure > 2000) OR
                  (T3Pressure > 2000) OR (T4Pressure > 2000);

IF AlarmHighPressure THEN
    CO2Vent := TRUE;
ELSIF (T1Pressure < 1350) AND (T2Pressure < 1350) AND
      (T3Pressure < 1350) AND (T4Pressure < 1350) THEN
    CO2Vent := FALSE;
END_IF;

IF AlarmEmergency THEN
    T1CIP := FALSE;
    T2CIP := FALSE;
    T3CIP := FALSE;
    T4CIP := FALSE;
END_IF;

IF CO2Header > 1200 AND NOT CO2Vent THEN
    CO2Recovery := TRUE;
ELSIF CO2Header < 1100 OR CO2Vent THEN
    CO2Recovery := FALSE;
END_IF;

T1FermentTimer(IN := T1PH <= 420, PT := T#10m);
T2FermentTimer(IN := T2PH <= 420, PT := T#10m);
T3FermentTimer(IN := T3PH <= 420, PT := T#10m);
T4FermentTimer(IN := T4PH <= 420, PT := T#10m);
T1Complete := T1FermentTimer.Q;
T2Complete := T2FermentTimer.Q;
T3Complete := T3FermentTimer.Q;
T4Complete := T4FermentTimer.Q;

IF (NOT T1Complete) OR T1CIP THEN T1Outlet := FALSE; END_IF;
IF (NOT T2Complete) OR T2CIP THEN T2Outlet := FALSE; END_IF;
IF (NOT T3Complete) OR T3CIP THEN T3Outlet := FALSE; END_IF;
IF (NOT T4Complete) OR T4CIP THEN T4Outlet := FALSE; END_IF;

END_PROGRAM

CONFIGURATION Config0
    RESOURCE Res0 ON PLC
        TASK task0(INTERVAL := T#100ms, PRIORITY := 0);
        PROGRAM instance0 WITH task0 : plc_prg;
    END_RESOURCE
END_CONFIGURATION
