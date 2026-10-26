PROGRAM plc_prg
VAR
    BBT1Temp       AT %QW0 : INT;
    BBT1Pressure   AT %QW1 : INT;
    BBT1Level      AT %QW2 : INT;
    BBT1Turbidity  AT %QW3 : INT;
    BBT2Temp       AT %QW10 : INT;
    BBT2Pressure   AT %QW11 : INT;
    BBT2Level      AT %QW12 : INT;
    BBT2Turbidity  AT %QW13 : INT;

    BBT1Glycol     AT %QX0.0 : BOOL;
    BBT1CO2Dose    AT %QX0.1 : BOOL;
    BBT1Outlet     AT %QX0.2 : BOOL;
    BBT1Vent       AT %QX0.3 : BOOL;
    BBT2Glycol     AT %QX1.2 : BOOL;
    BBT2CO2Dose    AT %QX1.3 : BOOL;
    BBT2Outlet     AT %QX1.4 : BOOL;
    BBT2Vent       AT %QX1.5 : BOOL;

    AlarmBBT1Temp      AT %QX2.4 : BOOL; (* coil 20 *)
    AlarmBBT2Temp      AT %QX2.5 : BOOL; (* coil 21 *)
    AlarmBBT1Pressure  AT %QX2.6 : BOOL; (* coil 22 *)
    AlarmBBT2Pressure  AT %QX2.7 : BOOL; (* coil 23 *)
    BBT1Ready          AT %QX3.0 : BOOL; (* coil 24 *)
    BBT2Ready          AT %QX3.1 : BOOL; (* coil 25 *)
END_VAR
VAR
    BBT1StableTimer : TON;
    BBT2StableTimer : TON;
END_VAR

AlarmBBT1Temp := BBT1Temp > 20;
AlarmBBT2Temp := BBT2Temp > 20;
AlarmBBT1Pressure := BBT1Pressure > 2000;
AlarmBBT2Pressure := BBT2Pressure > 2000;

IF BBT1Temp > 20 THEN BBT1Glycol := TRUE; ELSIF BBT1Temp <= 0 THEN BBT1Glycol := FALSE; END_IF;
IF BBT2Temp > 20 THEN BBT2Glycol := TRUE; ELSIF BBT2Temp <= 0 THEN BBT2Glycol := FALSE; END_IF;

IF BBT1Pressure > 2000 THEN BBT1CO2Dose := FALSE; END_IF;
IF BBT2Pressure > 2000 THEN BBT2CO2Dose := FALSE; END_IF;

IF BBT1Pressure >= 2500 THEN BBT1Vent := TRUE; ELSIF BBT1Pressure < 2200 THEN BBT1Vent := FALSE; END_IF;
IF BBT2Pressure >= 2500 THEN BBT2Vent := TRUE; ELSIF BBT2Pressure < 2200 THEN BBT2Vent := FALSE; END_IF;

BBT1StableTimer(IN := (BBT1Temp >= 0) AND (BBT1Temp <= 20) AND (BBT1Turbidity <= 20), PT := T#10m);
BBT2StableTimer(IN := (BBT2Temp >= 0) AND (BBT2Temp <= 20) AND (BBT2Turbidity <= 20), PT := T#10m);
BBT1Ready := BBT1StableTimer.Q;
BBT2Ready := BBT2StableTimer.Q;

IF NOT BBT1Ready THEN BBT1Outlet := FALSE; END_IF;
IF NOT BBT2Ready THEN BBT2Outlet := FALSE; END_IF;

IF BBT1Level <= 2 THEN BBT1Outlet := FALSE; END_IF;
IF BBT2Level <= 2 THEN BBT2Outlet := FALSE; END_IF;

END_PROGRAM

CONFIGURATION Config0
    RESOURCE Res0 ON PLC
        TASK task0(INTERVAL := T#100ms, PRIORITY := 0);
        PROGRAM instance0 WITH task0 : plc_prg;
    END_RESOURCE
END_CONFIGURATION
