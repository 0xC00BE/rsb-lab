#!/usr/bin/env python3
"""Initialize the two fresh FUXA instances, then verify editor authentication.

Run on the Docker host after creating its temporary management shims. This
operation refuses an existing project or existing local initialization marker.
Private administrator passwords are saved below LAB_DATA_DIR, never printed.
"""
import copy
import json
import secrets
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path
from lab import ROOT, check_configuration
from fuxa_project import assemble


def api(base, path, data=None, token=None):
    headers = {'Content-Type': 'application/json'}
    if token:
        headers['x-access-token'] = token
    request = urllib.request.Request(base + path,
        data=None if data is None else json.dumps(data).encode(), headers=headers)
    # Management addresses are local lab addresses; ignore proxy environment.
    with urllib.request.build_opener(urllib.request.ProxyHandler({})).open(request, timeout=45) as response:
        raw = response.read()
        return json.loads(raw) if raw else None


def main():
    state = Path(check_configuration()['LAB_DATA_DIR'])
    source = assemble()
    for role, address, container in [
        ('fuxa-hmi', '10.0.40.10', 'ics-fuxa-hmi'),
        ('fuxa-scada', '10.0.30.10', 'ics-fuxa-scada')]:
        marker = state / role / '.rsb-initialized'
        credentials = state / role / 'private-admin.json'
        if marker.exists() or credentials.exists():
            raise RuntimeError(f'{role} already initialized or partially initialized; inspect it before retrying.')
        base = f'http://{address}:1881'
        existing = api(base, '/api/project')
        if existing.get('hmi', {}).get('views'):
            raise RuntimeError(f'{role} has an existing project; refusing to replace it.')
        project = copy.deepcopy(source)
        if role == 'fuxa-scada':
            for device in project['devices'].values():
                if device.get('type') == 'BACnet':
                    device['enabled'] = False
        password, signing_key = secrets.token_urlsafe(28), secrets.token_hex(32)
        credentials.write_text(json.dumps({'username': 'admin', 'password': password}) + '\n')
        credentials.chmod(0o600)
        api(base, '/api/users', {'params': {'username': 'admin',
            'fullname': 'Lab Administrator', 'password': password, 'groups': -1, 'info': '{}'}})
        api(base, '/api/project', project)
        settings = state / role / 'appdata/settings.js'
        with settings.open('a') as output:
            output.write('\n// Generated local RSB authentication settings.\n')
            output.write('module.exports.secureEnabled = true;\n')
            output.write('module.exports.secretCode = ' + json.dumps(signing_key) + ';\n')
        subprocess.run(['docker', 'restart', container], check=True, stdout=subprocess.DEVNULL)
        for attempt in range(30):
            try:
                login = api(base, '/api/signin', {'username': 'admin', 'password': password})
                token = login['data']['token']
                break
            except (OSError, KeyError):
                if attempt == 29:
                    raise
                time.sleep(2)
        loaded = api(base, '/api/project', token=token)
        if len(loaded.get('hmi', {}).get('views', [])) != len(project['hmi']['views']):
            raise RuntimeError(f'{role}: project view count did not match.')
        # Submit the same project: if authorization is unexpectedly broken,
        # this still preserves the configuration while the validation fails.
        try:
            api(base, '/api/project', project)
        except urllib.error.HTTPError as error:
            if error.code not in (401, 403):
                raise
        else:
            raise RuntimeError(f'{role}: anonymous project writes were accepted!')
        api(base, '/api/project')  # Anonymous viewing must remain available.
        marker.write_text('Project imported; admin sign-in and anonymous write rejection verified.\n')
        print(f'{role}: imported {len(project["hmi"]["views"])} views; editor authentication verified.')


if __name__ == '__main__':
    main()
