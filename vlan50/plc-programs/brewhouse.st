PROGRAM plc_prg
VAR
    MashTemp           AT %QW0 : INT;
    MashLevel          AT %QW1 : INT;
    MashPH             AT %QW2 : INT;
    LauterTurbidity    AT %QW3 : INT;
    LauterLevel        AT %QW4 : INT;
    KettleTemp         AT %QW5 : INT;
    KettleLevel        AT %QW6 : INT;
    KettlePressure     AT %QW7 : INT;
    WhirlpoolTemp      AT %QW8 : INT;
    ChillerOutTemp     AT %QW9 : INT;

    MashAgitator       AT %QX0.0 : BOOL;
    MashOutlet         AT %QX0.1 : BOOL;
    LauterToKettle     AT %QX0.2 : BOOL;
    LauterRecirculate  AT %QX0.3 : BOOL;
    KettleSteam        AT %QX0.4 : BOOL;
    KettleToWhirlpool  AT %QX0.5 : BOOL;
    WhirlpoolOutlet    AT %QX0.6 : BOOL;
    ChillerOutlet      AT %QX0.7 : BOOL;

    AlarmTurbidity     AT %QX1.0 : BOOL;  (* coil 8 *)
    AlarmKettleTemp    AT %QX1.1 : BOOL;  (* coil 9 *)
    AlarmKettlePress   AT %QX1.2 : BOOL;  (* coil 10 *)
    AlarmChillerTemp   AT %QX1.3 : BOOL;  (* coil 11 *)
    WhirlpoolReady     AT %QX1.4 : BOOL;  (* coil 12 *)
END_VAR
VAR
    TransferSeen : BOOL;
    WhirlpoolRest : TON;
END_VAR

AlarmTurbidity   := LauterTurbidity > 200;
AlarmKettleTemp  := KettleTemp >= 1000;
AlarmKettlePress := KettlePressure >= 1200;
AlarmChillerTemp := ChillerOutTemp > 200;

IF AlarmTurbidity AND (LauterLevel > 2) THEN
    LauterToKettle := FALSE;
    LauterRecirculate := TRUE;
ELSIF LauterLevel <= 2 THEN
    LauterToKettle := FALSE;
    LauterRecirculate := FALSE;
END_IF;

IF AlarmKettleTemp OR AlarmKettlePress THEN
    KettleSteam := FALSE;
END_IF;

IF KettleToWhirlpool THEN
    TransferSeen := TRUE;
END_IF;

WhirlpoolRest(IN := TransferSeen AND NOT KettleToWhirlpool, PT := T#20m);
WhirlpoolReady := WhirlpoolRest.Q;

IF NOT WhirlpoolReady THEN
    WhirlpoolOutlet := FALSE;
END_IF;

IF AlarmChillerTemp THEN
    ChillerOutlet := FALSE;
END_IF;

IF ChillerOutlet AND (ChillerOutTemp <= 200) THEN
    TransferSeen := FALSE;
END_IF;

END_PROGRAM

CONFIGURATION Config0
    RESOURCE Res0 ON PLC
        TASK task0(INTERVAL := T#100ms, PRIORITY := 0);
        PROGRAM instance0 WITH task0 : plc_prg;
    END_RESOURCE
END_CONFIGURATION
