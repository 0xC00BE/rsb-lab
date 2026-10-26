#!/usr/bin/env python3
"""Static release checks. Does not contact or change a running lab."""
import ast
import ipaddress
import json
import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
SKIP = {'.git','.local','__pycache__','.venv','node_modules'}
FORBIDDEN_SUFFIXES = {'.ovpn','.pem','.key','.p12','.pfx','.exe','.dll','.zip','.gz','.qcow2','.vmdk','.vhdx','.ova','.iso','.sql'}

def check(root=ROOT):
    errors = []
    files = [p for p in root.rglob('*') if p.is_file() and not (set(p.relative_to(root).parts) & SKIP)]
    for p in files:
        rel = p.relative_to(root).as_posix()
        if p.name == '.env' or (p.name.startswith('.env.') and p.name != '.env.example'):
            # Runtime local secrets are allowed on disk but never in a release archive.
            continue
        if p.suffix.lower() in FORBIDDEN_SUFFIXES or re.search(r'known_hosts|conversation[-_]|CREDENTIALS_MASTER|RSB_LAB_CREDENTIALS',p.name,re.I):
            errors.append('Forbidden release file: '+rel)
        if p.stat().st_size > 10_000_000:
            errors.append('Review oversized release file: '+rel)
        try:
            text = p.read_text(encoding='utf-8-sig')
        except UnicodeError:
            errors.append('Unexpected binary file: '+rel)
            continue
        patterns = [r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----',
                    r'gh[pousr]_[A-Za-z0-9]{30,}', r'github_pat_[A-Za-z0-9_]{40,}',
                    r'AKIA[A-Z0-9]{16}', r'192\.168\.15\.(?:218|220)', r'10\.100\.0\.2']
        if any(re.search(pattern,text) for pattern in patterns):
            errors.append('Private material pattern: '+rel)
        try:
            if p.suffix in {'.json','.fuxap'}:
                json.loads(text)
            if p.suffix in {'.yaml','.yml'}:
                yaml.safe_load(text)
            if p.suffix == '.py':
                ast.parse(text,filename=rel)
        except (ValueError,SyntaxError,yaml.YAMLError) as error:
            errors.append(f'Parse failure: {rel}: {error}')
    all_addresses = set()
    for zone in [20,30,40,50]:
        path = root/f'vlan{zone}/compose.yaml'
        try:
            cfg = yaml.safe_load(path.read_text())
            declared = cfg['networks']
            if cfg['networks'][f'vlan{zone}']['driver_opts']['parent'] != '${VLAN'+str(zone)+'_PARENT:?Set the Linux network interface}':
                errors.append(f'Non-configurable interface in VLAN{zone}')
            for name,svc in cfg['services'].items():
                if svc.get('ports'):
                    errors.append(f'Unexpected host port publishing: {name}')
                for network, options in svc.get('networks',{}).items():
                    if network not in declared:
                        errors.append(f'Undeclared network: {name}/{network}')
                    if options and 'ipv4_address' in options:
                        address = options['ipv4_address']
                        if address in all_addresses:
                            errors.append('Duplicate address: '+address)
                        all_addresses.add(address)
                        if ipaddress.ip_address(address) not in ipaddress.ip_network(f'10.0.{zone}.0/24'):
                            errors.append('Address outside zone: '+address)
                for volume in svc.get('volumes',[]):
                    if volume.startswith('./') or volume.startswith('../'):
                        source = volume.split(':',1)[0]
                        if not (path.parent/source).exists():
                            errors.append(f'Missing mount source: {name}/{source}')
                build = svc.get('build')
                if build:
                    context = path.parent/build['context']
                    if not (context/build.get('dockerfile','Dockerfile')).is_file():
                        errors.append('Missing Dockerfile: '+name)
                if ':latest' in svc.get('image',''):
                    errors.append('Floating image tag: '+name)
        except (ValueError,KeyError,OSError,yaml.YAMLError) as error:
            errors.append(f'Compose structure failure VLAN{zone}: {error}')
    expected = {f'10.0.50.{n}' for n in range(101,107)}
    if not expected.issubset(all_addresses):
        errors.append('Missing PLC field addresses')
    scada=json.loads((root/'projects/scadalts/modbus.json').read_text())
    if len(scada['dataSources']) != 6 or len(scada['dataPoints']) != 142:
        errors.append('Unexpected Scada-LTS export counts')
    protocols=json.loads((root/'projects/scadalts/protocols.json').read_text())
    if len(protocols['dataSources']) != 2 or len(protocols['dataPoints']) != 17:
        errors.append('Unexpected native protocol export counts')
    flow=json.loads((root/'vlan20/flows/flows.json').read_text())
    ids={n['id'] for n in flow}
    for node in flow:
        if node['id'] == node['type']:
            errors.append('Node-RED node ID collides with its type: '+node['id'])
        if 'credentials' in node:
            errors.append('Credentials embedded in public flow: '+node['id'])
        for group in node.get('wires',[]):
            for target in group:
                if target not in ids:
                    errors.append('Broken Node-RED wire: '+target)
    accounts=json.loads((root/'lab/public-training-accounts.json').read_text())['accounts']
    ad=(root/'provisioning/windows/Implement-RSBAD.ps1').read_text()
    for account in accounts:
        if not account['password'].startswith('PublicLab!') or account['password'] not in ad:
            errors.append('Inconsistent public account: '+account['account'])
    policy=json.loads((root/'provisioning/firewall/policy.json').read_text())
    for rule in policy['rules']:
        for key in ['source','destination']:
            ipaddress.ip_network(rule[key],strict=False)
        if rule['source']=='10.0.10.0/24' and rule['port'] != '8088':
            errors.append('Overbroad corporate pivot policy')
    # Verify local Markdown links, including paths used as image references.
    for p in files:
        if p.suffix != '.md': continue
        for link in re.findall(r'!?\[[^\]]*\]\(([^)]+)\)',p.read_text(encoding='utf-8-sig')):
            link=link.split('#',1)[0]
            if not link or re.match(r'https?://|mailto:',link): continue
            if not (p.parent/link).exists():
                errors.append(f'Broken document link: {p.relative_to(root)} -> {link}')
    return len(files),errors

if __name__ == '__main__':
    count,errors=check()
    for error in errors:
        print('FAIL:',error)
    print(f'{count} files reviewed; {len(errors)} release check failures.')
    sys.exit(bool(errors))
