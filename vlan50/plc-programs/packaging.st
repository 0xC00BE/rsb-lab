PROGRAM plc_prg
VAR
    FilterDP       AT %QW0 : INT;
    FlowRate       AT %QW1 : INT;
    SourceLevel    AT %QW2 : INT;
    BottleCount    AT %QW3 : INT;
    CapTorque      AT %QW4 : INT;
    CaseCount      AT %QW5 : INT;

    FillerRun      AT %QX0.0 : BOOL;
    CIPActive      AT %QX0.1 : BOOL;
    CapperRun      AT %QX0.2 : BOOL;
    ConveyorZ1     AT %QX0.3 : BOOL;
    ConveyorZ2     AT %QX0.4 : BOOL;
    ConveyorZ3     AT %QX0.5 : BOOL;
    LineEStop      AT %QX0.6 : BOOL;
    RejectGate     AT %QX0.7 : BOOL;

    AlarmLowFlow   AT %QX1.0 : BOOL; (* coil 8 *)
    AlarmCapTorque AT %QX1.1 : BOOL; (* coil 9 *)
    AlarmFilterDP  AT %QX1.2 : BOOL; (* coil 10 *)
    AlarmLowLevel  AT %QX1.3 : BOOL; (* coil 11 *)
END_VAR
VAR
    FillerStartup : TON;
END_VAR

FillerStartup(IN := FillerRun AND NOT CIPActive AND NOT LineEStop, PT := T#10s);
AlarmLowFlow := FillerStartup.Q AND (FlowRate < 5);
AlarmCapTorque := FillerRun AND CapperRun AND ((CapTorque < 20) OR (CapTorque > 40));
AlarmFilterDP := FilterDP >= 400;
AlarmLowLevel := SourceLevel <= 5;
RejectGate := AlarmCapTorque;

IF CIPActive THEN
    FillerRun := FALSE;
    CapperRun := FALSE;
    ConveyorZ1 := FALSE;
    ConveyorZ2 := FALSE;
    ConveyorZ3 := FALSE;
END_IF;

IF AlarmLowFlow OR AlarmLowLevel THEN
    FillerRun := FALSE;
END_IF;

IF AlarmFilterDP THEN
    LineEStop := TRUE;
END_IF;

IF LineEStop THEN
    FillerRun := FALSE;
    CapperRun := FALSE;
    ConveyorZ1 := FALSE;
    ConveyorZ2 := FALSE;
    ConveyorZ3 := FALSE;
END_IF;

END_PROGRAM

CONFIGURATION Config0
    RESOURCE Res0 ON PLC
        TASK task0(INTERVAL := T#100ms, PRIORITY := 0);
        PROGRAM instance0 WITH task0 : plc_prg;
    END_RESOURCE
END_CONFIGURATION
