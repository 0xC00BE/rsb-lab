#!/usr/bin/env python3
"""Check representative allowed/blocked paths from actual container namespaces.

Run as root on the isolated Docker guest. --test-host-bypass temporarily adds
one /32 route inside Node-RED's namespace and always removes that exact route.
The optional check requires the temporary 10.0.20.254 management shim.
"""
import argparse
import concurrent.futures
import json
import subprocess
import sys

PROBE = '''import json,socket,sys
r={'connected':False,'error':None}
try:
 s=socket.create_connection((sys.argv[1],int(sys.argv[2])),2);s.close();r['connected']=True
except OSError as e:r['error']=type(e).__name__
print(json.dumps(r))
'''


def namespace(container):
    pid = subprocess.check_output(['docker', 'inspect', '--format', '{{.State.Pid}}', container], text=True).strip()
    if not pid.isdigit() or int(pid) < 1:
        raise RuntimeError(container + ' is not running')
    return ['nsenter', '--target', pid, '--net']


def probe(row):
    container, host, port, allowed = row
    result = json.loads(subprocess.check_output(namespace(container) +
        [sys.executable, '-c', PROBE, host, str(port)], text=True))
    result.update(container=container, host=host, port=port, expected_allowed=allowed)
    print(json.dumps(result), flush=True)
    if result['connected'] != allowed or (not allowed and result['error'] != 'TimeoutError'):
        raise RuntimeError('Unexpected network result: ' + str(row))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--test-host-bypass', action='store_true')
    args = parser.parse_args()
    rows = [
        ('ics-nodered', '10.0.50.101', 502, True),
        ('ics-nodered', '10.0.30.20', 8086, True),
        ('ics-nodered', '10.0.10.2', 445, False),
        ('ics-nodered', '10.0.40.12', 3389, False),
        ('ics-nodered', '10.0.50.116', 20000, False),
        ('ics-fuxa-hmi', '10.0.50.101', 502, True),
        ('ics-fuxa-hmi', '10.0.10.2', 445, False),
        ('ics-fuxa-scada', '10.0.50.101', 502, True),
        ('ics-fuxa-scada', '10.0.50.116', 20000, False),
        ('rsb-pentest-status', '10.0.50.102', 502, True),
        ('rsb-pentest-status', '10.0.50.101', 502, False),
    ]
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
        list(pool.map(probe, rows))
    if args.test_host_bypass:
        net = namespace('ics-nodered')
        destination = '10.0.40.12/32'
        existing = subprocess.check_output(net + ['ip', 'route', 'show', 'exact', destination], text=True).strip()
        if existing:
            raise RuntimeError('An explicit route already exists; refusing to modify it.')
        subprocess.run(net + ['ip', 'route', 'add', destination, 'via', '10.0.20.254'], check=True)
        try:
            probe(('ics-nodered', '10.0.40.12', 3389, False))
        finally:
            subprocess.run(net + ['ip', 'route', 'del', destination, 'via', '10.0.20.254'], check=True)
        print('Host forwarding bypass rejected; temporary route removed.')


if __name__ == '__main__':
    main()
