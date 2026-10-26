#!/usr/bin/env python3
"""Prevent the multi-homed Docker management guest from routing around the lab firewall."""
import argparse
import os
import subprocess
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tools'))
from lab import check_configuration

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply',action='store_true')
    parser.add_argument('--install-service',action='store_true')
    args=parser.parse_args()
    env=check_configuration()
    interfaces=[env[f'VLAN{z}_PARENT'] for z in [20,30,40,50]]+[f'rsb-mgmt{z}' for z in [20,30,40,50]]
    if not args.apply and not args.install_service:
        print('Will block host forwarding arriving on:',', '.join(interfaces))
        print('Container private bridge traffic and host-originated management traffic remain available.')
        return
    if os.geteuid()!=0: raise RuntimeError('Run as root on the dedicated Linux Docker guest.')
    if args.install_service:
        script=str(Path(__file__).resolve()).replace('\\','\\\\').replace('"','\\"')
        unit='''[Unit]
Description=RSB lab management host forwarding isolation
After=docker.service network-online.target
Requires=docker.service
[Service]
Type=oneshot
RemainAfterExit=yes
ExecStart=/usr/bin/python3 "'''+script+'''" --apply
[Install]
WantedBy=multi-user.target
'''
        Path('/etc/systemd/system/rsb-host-isolation.service').write_text(unit)
        subprocess.run(['systemctl','daemon-reload'],check=True)
        subprocess.run(['systemctl','enable','rsb-host-isolation.service'],check=True)
    for interface in interfaces:
        rule=['-i',interface,'-j','DROP']
        found=subprocess.run(['iptables','-C','DOCKER-USER',*rule],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        if found.returncode:
            subprocess.run(['iptables','-I','DOCKER-USER','1',*rule],check=True)
    print('Explicit host-forwarding isolation applied. Verify negative network paths after deployment.')

if __name__=='__main__': main()
