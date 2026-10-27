#!/usr/bin/env python3
"""Upgrade initialized RSB FUXA projects, retaining editor credentials and backups."""
import argparse
import copy
import json
from datetime import datetime,timezone
from pathlib import Path
from configure_fuxa import api
from fuxa_project import assemble
from lab import check_configuration


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply',action='store_true',help='Back up and replace the known RSB projects.')
    args=parser.parse_args()
    source=assemble()
    state=Path(check_configuration()['LAB_DATA_DIR'])
    for role,address in [('fuxa-hmi','10.0.40.10'),('fuxa-scada','10.0.30.10')]:
        credentials=json.loads((state/role/'private-admin.json').read_text())
        base=f'http://{address}:1881'
        token=api(base,'/api/signin',credentials)['data']['token']
        current=api(base,'/api/project',token=token)
        old_ids={v['id'] for v in current['hmi']['views']}
        new_ids={v['id'] for v in source['hmi']['views']}
        if not old_ids or not old_ids.issubset(new_ids) or set(current['devices'])!=set(source['devices']):
            raise RuntimeError(role+': project contains unrecognized views or devices; refusing to replace it.')
        print(f'{role}: {len(old_ids)} views -> {len(new_ids)} views; private credentials preserved.')
        if not args.apply:continue
        backup_dir=state/role/'backups';backup_dir.mkdir(exist_ok=True,mode=0o700)
        backup=backup_dir/('project-before-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')+'.json')
        with backup.open('x',encoding='utf-8') as output:json.dump(current,output)
        backup.chmod(0o600)
        project=copy.deepcopy(source)
        if role=='fuxa-scada':
            for device in project['devices'].values():
                if device.get('type')=='BACnet':device['enabled']=False
        try:
            api(base,'/api/project',project,token)
            loaded=api(base,'/api/project',token=token)
            expected={v['id']:v['svgcontent'] for v in project['hmi']['views']}
            actual={v['id']:v['svgcontent'] for v in loaded['hmi']['views']}
            if actual!=expected:raise RuntimeError('View/artwork readback differs from the source')
        except Exception:
            api(base,'/api/project',current,token)
            raise
        print(role+': full visual project saved and all view/artwork contents verified.')


if __name__=='__main__':main()
