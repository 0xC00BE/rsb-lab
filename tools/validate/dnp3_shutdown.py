#!/usr/bin/env python3
"""Exercise boiler command/evidence handling on a disposable isolated lab.

Requires --exercise-shutdown. Temporarily stop Scada-LTS's boiler source first
so this master can use address 2. Run with the Utilities image on an allowed
engineering network namespace. The finally block restores both permissives;
run reset-process afterward to clear the intentionally latched exercise state.
"""
import argparse
import os
import socket
import struct
import threading
import time
import sys
import traceback
from pydnp3 import opendnp3 as dnp, asiodnp3 as asio, asiopal, openpal
_native = []


def evidence():
    with socket.create_connection(('10.0.50.106', 502), 3) as stream:
        stream.sendall(struct.pack('>HHHBBHH', 191, 0, 6, 1, 3, 900, 9))

        def read(size):
            data = b''
            while len(data) < size:
                part = stream.recv(size - len(data))
                if not part:
                    raise RuntimeError('Incomplete evidence response')
                data += part
            return data

        header = read(7)
        body = read(struct.unpack('>H', header[4:6])[0] - 1)
        if body[:2] != bytes([3, 18]):
            raise RuntimeError('Unexpected evidence response')
        return list(struct.unpack('>9H', body[2:]))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--exercise-shutdown', action='store_true')
    args = parser.parse_args()
    if not args.exercise_shutdown:
        parser.error('Use --exercise-shutdown only on a disposable isolated lab.')
    initial = evidence()
    if initial[0] != 0:
        raise RuntimeError('The challenge is already latched; reset it before testing.')
    manager = asio.DNP3Manager(1, asio.ConsoleLogger().Create())
    channel = manager.AddTCPClient('validation', 0, asiopal.ChannelRetry().Default(),
        '10.0.50.116', '0.0.0.0', 20000, asio.PrintingChannelListener().Create())
    config = asio.MasterStackConfig()
    config.master.responseTimeout = openpal.TimeDuration().Seconds(2)
    config.link.LocalAddr, config.link.RemoteAddr = 2, 1
    master = channel.AddMaster('validation', asio.PrintingSOEHandler().Create(),
        asio.DefaultMasterApplication().Create(), config)
    _native.extend([manager, channel, master])
    master.Enable()

    def command(index, enabled):
        finished, success = threading.Event(), []

        def callback(result):
            success.append(result.summary == dnp.TaskCompletion.SUCCESS)
            finished.set()

        block = dnp.ControlRelayOutputBlock(dnp.ControlCode.LATCH_ON if enabled else dnp.ControlCode.LATCH_OFF)
        master.SelectAndOperate(block, index, callback, dnp.TaskConfig().Default())
        if not finished.wait(8) or not all(success):
            raise RuntimeError('DNP3 select/operate did not succeed')

    time.sleep(2)
    try:
        command(0, False)
        command(1, False)
        for _ in range(10):
            time.sleep(2)
            result = evidence()
            if result[0] == 1 and result[2] == 303 and result[5:7] == [1, 1]:
                print('DNP3 shutdown commands accepted; evidence latch/reason/permissives verified.', flush=True)
                break
        else:
            raise RuntimeError('Shutdown evidence did not latch; ensure a healthy baseline ran for over 40 seconds.')
    finally:
        errors = []
        try:
            for index in (0, 1):
                try:
                    command(index, True)
                except Exception as error:
                    errors.append(error)
            if errors:
                raise RuntimeError('A permissive could not be restored; reset the Utilities simulator.')
            print('Both DNP3 permissives restored. Reset the simulator to clear the latch.', flush=True)
        finally:
            master.Disable()


if __name__ == '__main__':
    code = 0
    try:
        main()
    except Exception:
        traceback.print_exc()
        code = 1
    # This is a short-lived validation client. Retain native references until
    # process exit: the pinned binding can deadlock during interpreter teardown
    # while its worker thread waits for the Python GIL. All command restoration
    # has completed before reaching here; process exit closes the client socket.
    sys.stdout.flush()
    sys.stderr.flush()
    os._exit(code)
