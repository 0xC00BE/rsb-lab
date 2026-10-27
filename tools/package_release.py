#!/usr/bin/env python3
"""Package only committed source, with a SHA-256 checksum. Never packages state."""
import argparse
import hashlib
import re
import subprocess
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('ref',help='Committed version or tag to package')
    parser.add_argument('--output',type=Path,default=ROOT/'.local/releases')
    args=parser.parse_args()
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]*',args.ref):
        raise RuntimeError('Use a simple tag or commit identifier.')
    dirty=subprocess.check_output(['git','status','--porcelain'],cwd=ROOT,text=True)
    if dirty:
        raise RuntimeError('Commit or preserve working changes before packaging.')
    args.output.mkdir(parents=True,exist_ok=True)
    name='rsb-lab-'+args.ref
    archive=args.output/(name+'.zip')
    subprocess.run(['git','archive','--format=zip','--prefix='+name+'/',
                    '--output='+str(archive.resolve()),args.ref],cwd=ROOT,check=True)
    digest=hashlib.sha256(archive.read_bytes()).hexdigest()
    archive.with_suffix('.zip.sha256').write_text(digest+'  '+archive.name+'\n',encoding='ascii')
    print(archive)
    print('SHA-256:',digest)

if __name__=='__main__': main()
