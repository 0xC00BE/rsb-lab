"""OpenDNP3 field interface. Remote commands never override PLC permissives."""
import logging
import math
import os
import threading
import time
from pydnp3 import opendnp3 as dnp, asiodnp3 as asio, asiopal, openpal

log = logging.getLogger('dnp3-boiler')


class Commands(dnp.ICommandHandler):
    def __init__(self, owner):
        super().__init__()
        self.owner = owner

    def Start(self):
        pass

    def End(self):
        pass

    def validate(self, command, index):
        if isinstance(command, dnp.ControlRelayOutputBlock):
            if index not in (0, 1):
                return dnp.CommandStatus.NOT_SUPPORTED
            if command.functionCode not in (dnp.ControlCode.LATCH_ON, dnp.ControlCode.LATCH_OFF):
                return dnp.CommandStatus.NOT_SUPPORTED
        elif isinstance(command, (dnp.AnalogOutputInt16, dnp.AnalogOutputInt32,
                                  dnp.AnalogOutputFloat32, dnp.AnalogOutputDouble64)):
            if index != 0:
                return dnp.CommandStatus.NOT_SUPPORTED
            if not math.isfinite(command.value) or not 0 <= command.value <= 9:
                return dnp.CommandStatus.OUT_OF_RANGE
        else:
            return dnp.CommandStatus.NOT_SUPPORTED
        return dnp.CommandStatus.SUCCESS

    def Select(self, command, index):
        # Select validates only; the stack enforces matching Select/Operate.
        return self.validate(command, index)

    def Operate(self, command, index, op_type):
        status = self.validate(command, index)
        if status != dnp.CommandStatus.SUCCESS:
            return status
        with self.owner.lock:
            if isinstance(command, dnp.ControlRelayOutputBlock):
                key = ('burner_enable', 'pump_enable')[index]
                value = command.functionCode == dnp.ControlCode.LATCH_ON
            else:
                key, value = 'setpoint', float(command.value)
            self.owner.control[key] = value
        log.info('Command accepted: %s=%s (%s)', key, value, op_type)
        return status


class BoilerOutstation:
    def __init__(self):
        self.lock = threading.Lock()
        self.control = dict(setpoint=7.0, burner_enable=True, pump_enable=True)
        self.logger = asio.ConsoleLogger().Create()
        self.manager = asio.DNP3Manager(1, self.logger)
        self.listener = asio.PrintingChannelListener().Create()
        self.channel = self.manager.AddTCPServer('RSB-Boiler', dnp.levels.NORMAL,
            asiopal.ChannelRetry().Default(), os.environ.get('DNP3_BIND', '10.0.50.116'),
            int(os.environ.get('DNP3_PORT', '20000')), self.listener)
        sizes = dnp.DatabaseSizes(2, 0, 4, 0, 0, 2, 1, 0)
        config = asio.OutstationStackConfig(sizes)
        config.outstation.eventBufferConfig = dnp.EventBufferConfig().AllTypes(20)
        config.outstation.params.allowUnsolicited = False
        config.link.LocalAddr = int(os.environ.get('DNP3_OUTSTATION_ADDR', '1'))
        config.link.RemoteAddr = int(os.environ.get('DNP3_MASTER_ADDR', '2'))
        config.link.KeepAliveTimeout = openpal.TimeDuration().Max()
        for i in range(4):
            config.dbConfig.analog[i].svariation = dnp.StaticAnalogVariation.Group30Var5
            config.dbConfig.analog[i].evariation = dnp.EventAnalogVariation.Group32Var7
            config.dbConfig.analog[i].clazz = dnp.PointClass.Class2
            config.dbConfig.analog[i].deadband = 0.1
        self.handler = Commands(self)
        self.application = dnp.DefaultOutstationApplication.Create()
        self.outstation = self.channel.AddOutstation('boiler', self.handler, self.application, config)
        self.outstation.Enable()
        log.info('DNP3 outstation=%s master=%s configured', config.link.LocalAddr, config.link.RemoteAddr)

    def commands(self):
        with self.lock:
            return dict(self.control)

    def publish(self, state, pump_run):
        update = asio.UpdateBuilder()
        # Preserve the original plan's pressure scaling (raw / 10 = bar).
        for index, value in enumerate((state['drum_press'] * 10,
                state['header_press'] * 10, state['flue_temp'], state['fw_level'])):
            update.Update(dnp.Analog(value), index)
        update.Update(dnp.Binary(state['burner_run']), 0)
        update.Update(dnp.Binary(state['relief_open']), 1)
        command = self.commands()
        update.Update(dnp.AnalogOutputStatus(command['setpoint']), 0)
        update.Update(dnp.BinaryOutputStatus(command['burner_enable']), 0)
        update.Update(dnp.BinaryOutputStatus(command['pump_enable']), 1)
        self.outstation.Apply(update.Build())
        with open('/tmp/dnp3-heartbeat', 'w') as f:
            f.write(str(time.time()))
