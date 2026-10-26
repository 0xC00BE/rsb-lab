#!/usr/bin/env python3
"""Optional Linux host-to-macvlan management access; run as root after init."""
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]/'tools'))
from lab import check_configuration

def main():
    env = check_configuration()
    for zone in [20,30,40,50]:
        name = f'rsb-mgmt{zone}'
        if Path('/sys/class/net',name).exists():
            raise RuntimeError(f'{name} already exists; inspect it manually before changing anything.')
    for zone in [20,30,40,50]:
        name = f'rsb-mgmt{zone}'
        subprocess.run(['ip','link','add',name,'link',env[f'VLAN{zone}_PARENT'],'type','macvlan','mode','bridge'],check=True)
        subprocess.run(['ip','addr','add',f'10.0.{zone}.254/24','dev',name],check=True)
        subprocess.run(['ip','link','set',name,'up'],check=True)
    print('Created temporary management interfaces. These do not survive reboot; see docs/networking.md.')

if __name__ == '__main__':
    main()
