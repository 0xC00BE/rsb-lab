#!/usr/bin/env python3
"""Local lab lifecycle. Python standard library only; no hypervisor assumptions."""
import argparse
import json
import os
import re
import secrets
import shutil
import subprocess
import sys
from pathlib import Path, PurePosixPath
from xml.sax.saxutils import escape

ROOT = Path(__file__).resolve().parents[1]
ZONES = [20, 30, 40, 50]

def run(args, **kwargs):
    return subprocess.run([str(a) for a in args], check=True, **kwargs)

def env_file():
    path = ROOT / '.env'
    if not path.exists():
        raise RuntimeError('Run: python3 tools/lab.py init')
    result = {}
    for line in path.read_text().splitlines():
        if line.strip() and not line.lstrip().startswith('#'):
            k, v = line.split('=', 1)
            result[k] = v
    return result

def compose(zone, *args):
    run(['docker', 'compose', '--env-file', ROOT / '.env', '-p', f'rsb-vlan{zone}',
         '-f', ROOT / f'vlan{zone}/compose.yaml', *args], cwd=ROOT)

def init():
    if (ROOT / '.env').exists():
        raise RuntimeError('.env already exists; edit it in place. Nothing was overwritten.')
    text = (ROOT / '.env.example').read_text().replace('CHANGE_ME_ABSOLUTE_LINUX_STATE_DIRECTORY',
                                                      (ROOT / '.local/state').as_posix())
    text = re.sub(r'=GENERATED_BY_INIT', lambda m: '=' + secrets.token_hex(24), text)
    fd = os.open(ROOT / '.env', os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'w', encoding='utf-8', newline='\n') as f:
        f.write(text)
    print('Created local .env. Set the four VLAN*_PARENT values before proceeding.')

def check_configuration(linux=True):
    values = env_file()
    if any('CHANGE_ME' in v or 'GENERATED_BY_INIT' in v for v in values.values()):
        raise RuntimeError('Edit .env and replace all placeholders first.')
    state = PurePosixPath(values['LAB_DATA_DIR'])
    if not state.is_absolute() or state == PurePosixPath('/') or ':' in str(state) or '..' in state.parts:
        raise RuntimeError('LAB_DATA_DIR must be an absolute Linux directory below a filesystem root.')
    parents = [values[f'VLAN{v}_PARENT'] for v in ZONES]
    if len(set(parents)) != len(parents) or any(not re.fullmatch(r'[A-Za-z0-9_.:-]{1,15}', p) for p in parents):
        raise RuntimeError('Provide four different Linux interfaces or VLAN subinterfaces.')
    for key, value in values.items():
        if key.endswith('_IMAGE') and not re.fullmatch(r'[^\s]+@sha256:[0-9a-f]{64}', value):
            raise RuntimeError(f'{key} must be pinned by sha256 digest.')
    if linux:
        if not sys.platform.startswith('linux'):
            raise RuntimeError('Run deployment commands inside the Linux Docker VM.')
        if Path(values['LAB_DATA_DIR']).resolve() == Path('/'):
            raise RuntimeError('State directory resolves to the filesystem root.')
        resolved_state = Path(values['LAB_DATA_DIR']).resolve()
        if resolved_state.is_relative_to(ROOT.resolve()) and not resolved_state.is_relative_to((ROOT / '.local').resolve()):
            raise RuntimeError('Keep private state below the ignored .local directory or outside the source checkout.')
        for parent in parents:
            if not (Path('/sys/class/net') / parent).exists():
                raise RuntimeError(f'Linux interface is missing: {parent}')
        run(['docker', 'info'], stdout=subprocess.DEVNULL)
        for zone in ZONES:
            compose(zone, 'config', '--quiet')
    return values

def prepare_state():
    e = check_configuration()
    state = Path(e['LAB_DATA_DIR'])
    marker = state / '.rsb-lab-state'
    if state.exists() and any(state.iterdir()) and not marker.is_file():
        raise RuntimeError('Refusing an existing nonempty directory without an RSB state marker. Choose a new dedicated directory.')
    state.mkdir(parents=True, exist_ok=True)
    state.chmod(0o700)
    marker.touch(exist_ok=True)
    if os.environ.get('SUDO_UID'):
        os.chown(state, int(os.environ['SUDO_UID']), int(os.environ.get('SUDO_GID', os.environ['SUDO_UID'])))
    dirs = ['node-red/data', 'mosquitto/config', 'influxdb/data', 'influxdb/config',
            'grafana/data', 'mariadb/data', 'scadalts/logs', 'scadalts/context']
    for role in ['fuxa-hmi', 'fuxa-scada']:
        dirs += [f'{role}/{d}' for d in ['appdata','db','logs','images']]
    dirs += [f'openplc/{c}' for c in ['rawmat','brewhouse','fermentation','conditioning','packaging','utilities']]
    for d in dirs:
        (state / d).mkdir(parents=True, exist_ok=True)
    # Initialization never overwrites flow edits, database contents, or credentials.
    flow = state / 'node-red/data/flows.json'
    admin_hash = state / 'node-red/data/admin.hash'
    if not admin_hash.exists():
        accounts = json.loads((ROOT/'lab/public-training-accounts.json').read_text())['accounts']
        password = next(a['password'] for a in accounts if a['account']=='svc.nodered')
        code = "let s='';process.stdin.on('data',x=>s+=x);process.stdin.on('end',()=>console.log(require('bcryptjs').hashSync(s.trim(),12)));"
        hashed = subprocess.check_output(['docker','run','--rm','-i','--entrypoint','node',
                                          'rsb-nodered:source-v0.1.0','-e',code], input=password+'\n', text=True)
        admin_hash.write_text(hashed.strip()+'\n')
        admin_hash.chmod(0o600)
    if not flow.exists():
        shutil.copyfile(ROOT / 'vlan20/flows/flows.json', flow)
    cred = state / 'node-red/data/flows_cred.json'
    if not cred.exists():
        cred.write_text(json.dumps({'influx-out': {'token':e['INFLUXDB_TOKEN']},
                                   'rsb-mqtt-config': {'user':'rsb_broker','password':e['MQTT_PASSWORD']}}))
        cred.chmod(0o600)
    shutil.copyfile(ROOT/'vlan20/mosquitto/config/mosquitto.conf', state/'mosquitto/config/mosquitto.conf')
    passwd = state / 'mosquitto/config/passwd'
    if not passwd.exists():
        run(['docker','run','--rm','-i','--user','0','-v',f'{state}/mosquitto/config:/mosquitto/config',
             '--entrypoint','sh',e['MOSQUITTO_IMAGE'],'-c',
             'read -r password; mosquitto_passwd -b -c /mosquitto/config/passwd rsb_broker "$password"; chmod 644 /mosquitto/config/passwd'],
             input=e['MQTT_PASSWORD']+'\n', text=True)
    context = state / 'scadalts/context/context.xml'
    if not context.exists():
        context.write_text('''<?xml version="1.0" encoding="UTF-8"?>
<Context><Resource name="jdbc/scadalts" auth="Container" type="javax.sql.DataSource"
  factory="org.apache.tomcat.jdbc.pool.DataSourceFactory"
  driverClassName="com.mysql.jdbc.Driver"
  url="jdbc:mysql://mariadb:3306/scadalts?useUnicode=true&amp;characterEncoding=UTF-8&amp;useSSL=false"
  username="scadalts" password="''' + escape(e['MYSQL_PASSWORD'], {'"':'&quot;'}) + '''"
  maxActive="100" maxIdle="30" maxWait="10000" testOnBorrow="true" validationQuery="SELECT 1" />
</Context>\n''')
        context.chmod(0o644)  # Container must read it. Keep the state parent private.
    for d, uid in [('node-red/data',1000),('grafana/data',472)]:
        for path in [state / d, *(state / d).rglob('*')]:
            os.chown(path, uid, uid)
    print('Prepared persistent state. Keep this directory private and out of Git.')

def programs():
    check_configuration()
    for cell in ['rawmat','brewhouse','fermentation','conditioning','packaging','utilities']:
        container = 'ics-plc-' + cell
        run(['docker','cp',ROOT/f'vlan50/plc-programs/{cell}.st',container+':/tmp/program.st'])
        run(['docker','cp',ROOT/'vlan50/deploy-openplc.sh',container+':/tmp/deploy-openplc.sh'])
        run(['docker','exec',container,'bash','/tmp/deploy-openplc.sh','/tmp/program.st',cell,'RSB public source release'])

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['init','preflight','prepare-state','build','start','programs','stop','status','check','reset-process'])
    args = parser.parse_args()
    if args.action == 'init':
        return init()
    if args.action == 'prepare-state':
        return prepare_state()
    if args.action == 'programs':
        return programs()
    e = check_configuration()
    if args.action == 'preflight':
        print('Configuration and Docker Compose checks passed. Network policy and fresh deployment still need validation.')
    elif args.action == 'build':
        # Pull runtime images while the operator's temporary build connection
        # is available, so startup does not depend on internet access.
        for key,value in e.items():
            if key.endswith('_IMAGE'):
                run(['docker','pull',value])
        run([sys.executable, ROOT/'tools/build_openplc.py'])
        for v in ZONES:
            compose(v,'build')
    elif args.action == 'start':
        if not (Path(e['LAB_DATA_DIR'])/'scadalts/context/context.xml').is_file():
            raise RuntimeError('Run prepare-state first.')
        for v in [50,40,30,20]:
            compose(v,'up','-d','--no-build','--pull','never')
        print('Containers started. First installation: run programs, import projects, then check.')
    elif args.action == 'stop':
        for v in reversed(ZONES):
            compose(v,'stop')
    elif args.action == 'status':
        for v in ZONES:
            compose(v,'ps')
    elif args.action == 'check':
        run(['docker','exec','-i','ics-fuxa-hmi','node'],input=(ROOT/'tools/validate/smoke_test_ics_node.js').read_text(),text=True)
    elif args.action == 'reset-process':
        print('Resetting three challenge simulators; PLC commands and Windows/domain state are retained.')
        run(['docker','restart','ics-sim-brewhouse','ics-sim-fermentation','ics-sim-utilities'])
        print('Use coordinated clean VM snapshots for a full exercise reset. See docs/reset.md.')

if __name__ == '__main__':
    try:
        main()
    except (RuntimeError, OSError, subprocess.CalledProcessError) as error:
        print('ERROR:', error, file=sys.stderr)
        sys.exit(1)
