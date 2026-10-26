"""BACnet/IP field interface for the existing conditioning physics model."""
import asyncio
import logging
import math
import os
import threading
import time
from bacpypes3.app import Application
from bacpypes3.argparse import SimpleArgumentParser
from bacpypes3.local.analog import AnalogInputObject, AnalogOutputObject
from bacpypes3.local.binary import BinaryInputObject, BinaryOutputObject
from bacpypes3.errors import ExecutionError

log = logging.getLogger('bacnet-chiller')


class ReadOnlyValue:
    async def write_property(self, attr, value, index=None, priority=None):
        if isinstance(attr, int):
            attr = self._property_identifier_class(attr).attr
        if attr == 'presentValue':
            raise ExecutionError(errorClass='property', errorCode='writeAccessDenied')
        return await super().write_property(attr, value, index, priority)


class SensorAnalog(ReadOnlyValue, AnalogInputObject):
    pass


class SensorBinary(ReadOnlyValue, BinaryInputObject):
    pass


class Setpoint(AnalogOutputObject):
    async def write_property(self, attr, value, index=None, priority=None):
        if isinstance(attr, int):
            attr = self._property_identifier_class(attr).attr
        if attr == 'presentValue' and value is not None:
            try:
                v = float(value)
            except (TypeError, ValueError):
                v = None  # BACnet Null relinquishes a priority slot.
            if v is not None and (not math.isfinite(v) or not -5 <= v <= 20):
                raise ExecutionError(errorClass='property', errorCode='valueOutOfRange')
        return await super().write_property(attr, value, index, priority)


async def serve(sim, device_id, ready, state):
    args = SimpleArgumentParser().parse_args([
        '--address', os.environ.get('BACNET_ADDRESS', '10.0.50.114/24'),
        '--instance', str(device_id), '--name', 'RSB-Glycol-Chiller',
    ])
    app = Application.from_args(args)
    state['app'] = app
    common = dict(statusFlags=[0, 0, 0, 0], eventState='normal', outOfService=False)
    points = {}
    for idx, name, unit in [(1, 'glycolSupplyTemp', 'degreesCelsius'),
                            (2, 'glycolReturnTemp', 'degreesCelsius'),
                            (3, 'glycolFlow', 'litersPerSecond')]:
        points[name] = SensorAnalog(objectIdentifier=('analogInput', idx),
            objectName=name, presentValue=0.0, units=unit, covIncrement=0.1, **common)
    for idx, name in [(1, 'chillerRunStatus'), (2, 'faultAlarm')]:
        points[name] = SensorBinary(objectIdentifier=('binaryInput', idx),
            objectName=name, presentValue='inactive', polarity='normal', **common)
    points['tempSetpoint'] = Setpoint(objectIdentifier=('analogOutput', 1),
        objectName='tempSetpoint', presentValue=1.0, relinquishDefault=1.0,
        units='degreesCelsius', covIncrement=0.1, **common)
    for idx, name in [(1, 'chillerEnable'), (2, 'pumpEnable')]:
        points[name] = BinaryOutputObject(objectIdentifier=('binaryOutput', idx),
            objectName=name, presentValue='active', relinquishDefault='active',
            polarity='normal', **common)
    for point in points.values():
        app.add_object(point)
    ready.set()
    log.info('BACnet device %s listening on %s', device_id, args.address)
    previous = None
    return_temp = sim.glycol_supply_temp[0] + 2
    try:
        while sim.running:
            command = (float(points['tempSetpoint'].presentValue),
                       int(points['chillerEnable'].presentValue) == 1,
                       int(points['pumpEnable'].presentValue) == 1)
            sim.chiller_setpoint[0], sim.chiller_running[0], sim.chiller_pump[0] = command
            if previous is not None and command != previous:
                log.info('Command changed: setpoint=%s chiller=%s pump=%s', *command)
            previous = command
            supply = sim.glycol_supply_temp[0]
            return_temp += (supply + 2 - return_temp) * 0.1
            points['glycolSupplyTemp'].presentValue = round(supply, 2)
            points['glycolReturnTemp'].presentValue = round(return_temp, 2)
            points['glycolFlow'].presentValue = 2.5 if sim.chiller_pump[0] else 0.0
            points['chillerRunStatus'].presentValue = 'active' if command[1] and not sim.chiller_fault[0] else 'inactive'
            points['faultAlarm'].presentValue = 'active' if sim.chiller_fault[0] else 'inactive'
            # A heartbeat reflects the protocol loop, not merely an open UDP port.
            with open('/tmp/bacnet-heartbeat', 'w') as f:
                f.write(str(time.time()))
            await asyncio.sleep(1)
    finally:
        app.close()


def start_bacnet(sim, device_id):
    ready, state = threading.Event(), {}
    def worker():
        try:
            asyncio.run(serve(sim, device_id, ready, state))
        except Exception as exc:
            state['error'] = exc
            log.exception('BACnet server failed')
            ready.set()
    thread = threading.Thread(target=worker, daemon=True, name='bacnet-server')
    thread.start()
    if not ready.wait(15):
        raise RuntimeError('BACnet startup timed out')
    if 'error' in state:
        raise RuntimeError('BACnet startup failed') from state['error']
    return state
