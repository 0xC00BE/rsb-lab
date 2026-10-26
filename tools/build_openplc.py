#!/usr/bin/env python3
"""Build the pinned OpenPLC upstream locally; do not redistribute its binaries here."""
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def main():
    source = ROOT / '.local/build/OpenPLC_v3'
    pin = json.loads((ROOT/'lab/upstreams.lock.json').read_text())['upstreams']['openplc']
    source.mkdir(parents=True, exist_ok=True)
    if not (source/'.git').exists():
        subprocess.run(['git','init',str(source)],check=True)
        subprocess.run(['git','-C',str(source),'remote','add','origin',pin['repository']],check=True)
    remote = subprocess.check_output(['git','-C',str(source),'remote','get-url','origin'],text=True).strip()
    if remote != pin['repository']:
        raise RuntimeError('Build directory has a different upstream remote.')
    dirty = subprocess.check_output(['git','-C',str(source),'status','--porcelain'],text=True)
    if dirty:
        raise RuntimeError('OpenPLC build checkout has local changes; preserve them before rebuilding.')
    subprocess.run(['git','-C',str(source),'fetch','--depth','1','origin',pin['commit']],check=True)
    subprocess.run(['git','-C',str(source),'checkout','--detach',pin['commit']],check=True)
    # Bullseye's live security mirror no longer serves every package referenced
    # by its final metadata. Use a dated, signed Debian snapshot for this legacy
    # training runtime. Keep the upstream checkout clean and the adaptation explicit.
    snapshot='20260831T000000Z'
    base='debian@sha256:7aef2e7d061743fdb57973dac3ddbceb0b0912746ca7e0ee7535016c38286561'
    original=(source/'Dockerfile').read_text()
    expected='FROM debian:bullseye-20240722'
    if not original.startswith(expected+'\n'):
        raise RuntimeError('Upstream Dockerfile changed; review the legacy build adaptation.')
    lines=[f'deb [check-valid-until=no] http://snapshot.debian.org/archive/debian/{snapshot}/ bullseye main',
           f'deb [check-valid-until=no] http://snapshot.debian.org/archive/debian-security/{snapshot}/ bullseye-security main']
    setup='RUN printf "%s\\n" "'+lines[0]+'" "'+lines[1]+'" > /etc/apt/sources.list\n'
    generated=ROOT/'.local/build/openplc.Dockerfile'
    generated.write_text(original.replace(expected+'\n','FROM '+base+'\n'+setup,1))
    subprocess.run(['docker','build','-f',str(generated),'-t','rsb-openplc:source-v0.1.0',str(source)],check=True)

if __name__ == '__main__':
    main()
