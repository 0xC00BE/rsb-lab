#!/usr/bin/env python3
"""Import the public Modbus, BACnet and DNP3 projects into fresh Scada-LTS."""
import argparse
import getpass
import json
import secrets
import time
from pathlib import Path
from lab import ROOT, check_configuration
from scadalts_client import ScadaClient


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--url', default='http://10.0.40.20:8080/Scada-LTS/')
    parser.add_argument('--username', default='admin')
    parser.add_argument('--fresh-default-login', action='store_true',
        help='Use upstream public admin/admin credentials on a new isolated instance.')
    args = parser.parse_args()
    password = 'admin' if args.fresh_default_login else getpass.getpass('Scada-LTS password: ')
    client = ScadaClient(args.url, args.username, password)
    if client.rest('datasources') or client.rest('datapoints'):
        raise RuntimeError('Existing sources or points found; refusing to replace configuration.')
    for filename in ['modbus.json', 'protocols.json']:
        project = json.loads((ROOT / 'projects/scadalts' / filename).read_text())
        result = client.dwr('EmportDwr', 'importData', [client.string(json.dumps(project))])
        if 'importStarted=true' not in result:
            raise RuntimeError('Import did not start: ' + result[:500])
        for _ in range(60):
            time.sleep(2)
            result = client.dwr('EmportDwr', 'importUpdate')
            if 'complete=true' in result:
                break
        else:
            raise RuntimeError('Import did not finish; inspect Scada-LTS import messages.')
    if len(client.rest('datasources')) != 8 or len(client.rest('datapoints')) != 159:
        raise RuntimeError('Imported source/point counts differ from the public project.')
    if args.fresh_default_login:
        credential_path = Path(check_configuration()['LAB_DATA_DIR']) / 'scadalts/private-admin.json'
        if credential_path.exists():
            raise RuntimeError('Private administrator file already exists; inspect before rotating.')
        # The pinned login form accepts at most 20 characters.
        password = 'R!' + secrets.token_urlsafe(12) + 'a9'
        credential_path.write_text(json.dumps({'username': 'admin', 'password': password}) + '\n')
        credential_path.chmod(0o600)
        client.set_fresh_admin_password(password)
        print('Private SCADA administrator password generated and fresh login verified.')
    print('Imported eight sources and 159 points. Verify live values after firewall setup.')


if __name__ == '__main__':
    main()
