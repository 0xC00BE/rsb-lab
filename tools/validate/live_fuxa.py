#!/usr/bin/env python3
"""Read dashboard device values through the anonymous Socket.IO viewer API."""
import json
import time
import urllib.parse
import urllib.request


def check(address):
    base = f'http://{address}:1881'
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))

    def request(path, body=None):
        req = urllib.request.Request(base + path, data=None if body is None else body.encode(),
            headers={'Content-Type': 'text/plain;charset=UTF-8'})
        with opener.open(req, timeout=8) as response:
            return response.read().decode()

    project = json.loads(request('/api/project'))
    devices = project['devices']
    tag_ids = [t['id'] for d in devices.values() for t in d.get('tags', {}).values()]
    opened = request('/socket.io/?EIO=4&transport=polling')
    assert opened.startswith('0'), 'Engine.IO handshake failed'
    sid = json.loads(opened[1:])['sid']
    path = '/socket.io/?' + urllib.parse.urlencode({'EIO': 4, 'transport': 'polling', 'sid': sid})
    values, statuses, write_rejected = {}, {}, False
    try:
        request(path, '40')
        request(path)
        for event, payload in [
            ('device-tags-subscribe', {'tagsId': tag_ids, 'sendLastValue': True}),
            ('device-status', 'get'),
            ('device-values', {'cmd': 'set', 'var': {'source': 'rsb-validation-nonexistent',
                'id': 'rsb-validation-nonexistent', 'value': 0}})]:
            request(path, '42' + json.dumps([event, payload]))
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            for packet in request(path).split('\x1e'):
                if packet == '2':
                    request(path, '3')
                elif packet.startswith('42'):
                    event, data = json.loads(packet[2:])
                    if event == 'device-status':
                        statuses[data['id']] = data['status']
                    elif event == 'device-values':
                        if data.get('cmd') == 'set-unauthorized':
                            write_rejected = True
                        elif data.get('values'):
                            values[data['id']] = data['values']
            expected = [k for k, d in devices.items()
                        if d['type'] in ('ModbusTCP', 'BACnet') and d.get('enabled', True)]
            if all(k in values and k in statuses for k in expected) and write_rejected:
                break
        result = [{'device': devices[k]['name'], 'status': statuses.get(k),
                   'values': len(values.get(k, []))} for k in expected]
        print(json.dumps({'address': address, 'devices': result,
                          'anonymous_value_write_rejected': write_rejected}, indent=2))
        assert all(k in values and k in statuses for k in expected), 'Missing runtime device values/status'
        assert all(statuses[k] == 'connect-ok' and values[k] for k in expected), 'A dashboard device is disconnected'
        assert write_rejected, 'Anonymous Socket.IO write was not rejected'
    finally:
        request(path, '41')


if __name__ == '__main__':
    for address in ['10.0.40.10', '10.0.30.10']:
        check(address)
