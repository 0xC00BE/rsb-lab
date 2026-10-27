PROGRAM plc_prg
VAR
    Silo1_kg       AT %QW0 : INT;
    Silo2_kg       AT %QW1 : INT;
    MillRPM        AT %QW2 : INT;
    AugerCurrent   AT %QW3 : INT;
    HLT_Temp       AT %QW4 : INT;
    HLT_Level      AT %QW5 : INT;
    HLT_Flow       AT %QW6 : INT;
    CLT_Temp       AT %QW7 : INT;
    CLT_Level      AT %QW8 : INT;

    MillMotor      AT %QX0.0 : BOOL;
    AugerMotor     AT %QX0.1 : BOOL;
    HLT_Heater     AT %QX0.2 : BOOL;
    HLT_Valve      AT %QX0.3 : BOOL;
    CLT_Valve      AT %QX0.4 : BOOL;

    AlarmSiloLow   AT %QX1.0 : BOOL;  (* coil 8 *)
    AlarmAugerJam  AT %QX1.1 : BOOL;  (* coil 9 *)
    AlarmHLTHigh   AT %QX1.2 : BOOL;  (* coil 10 *)
    AlarmTankLow   AT %QX1.3 : BOOL;  (* coil 11 *)
END_VAR

AlarmSiloLow  := (Silo1_kg < 500) AND (Silo2_kg < 500);
AlarmAugerJam := AugerCurrent >= 100;   (* 10.0 A *)
AlarmHLTHigh  := HLT_Temp >= 780;       (* 78.0 C *)
AlarmTankLow  := (HLT_Level <= 5) OR (CLT_Level <= 5);

IF AlarmSiloLow OR AlarmAugerJam THEN
    MillMotor := FALSE;
    AugerMotor := FALSE;
END_IF;

IF AlarmHLTHigh THEN
    HLT_Heater := FALSE;
END_IF;

IF HLT_Level <= 5 THEN
    HLT_Valve := FALSE;
END_IF;

IF CLT_Level <= 5 THEN
    CLT_Valve := FALSE;
END_IF;

END_PROGRAM

CONFIGURATION Config0
    RESOURCE Res0 ON PLC
        TASK task0(INTERVAL := T#100ms, PRIORITY := 0);
        PROGRAM instance0 WITH task0 : plc_prg;
    END_RESOURCE
END_CONFIGURATION
