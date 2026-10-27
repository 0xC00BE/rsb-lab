#!/usr/bin/env python3
"""Download the checksum-pinned Ubuntu OVA into a private media directory."""
import argparse
import hashlib
import json
import time
import urllib.request
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]


def digest(path):
    with path.open('rb') as source:return hashlib.file_digest(source,'sha256').hexdigest()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory',type=Path,default=ROOT/'.local/media')
    args=parser.parse_args();directory=args.directory.resolve()
    if directory.is_relative_to(ROOT) and not directory.is_relative_to(ROOT/'.local'):
        raise ValueError('Keep OS media in ignored .local or outside the source checkout')
    spec=json.loads((ROOT/'lab/os-media.lock.json').read_text())['ubuntu_server']
    directory.mkdir(parents=True,exist_ok=True);out=directory/spec['filename']
    if out.exists():
        if out.stat().st_size!=spec['bytes'] or digest(out)!=spec['sha256']:
            raise ValueError('Existing media differs from the lock; inspect it rather than overwriting it')
        print('Existing Ubuntu OVA verified:',out);return
    partial=out.with_suffix('.ova.part')
    if partial.exists():raise ValueError('An incomplete download exists; inspect or remove it before retrying')
    started=last=time.monotonic();total=0;checksum=hashlib.sha256()
    with urllib.request.urlopen(spec['url'],timeout=60) as response,partial.open('xb') as target:
        if not response.url.startswith('https://'):raise ValueError('Refusing an unencrypted media redirect')
        while chunk:=response.read(4*1024*1024):
            total+=len(chunk)
            if total>spec['bytes']:raise ValueError('Downloaded media exceeds its locked size')
            target.write(chunk);checksum.update(chunk)
            if time.monotonic()-last>20:
                print('Downloaded MiB:',round(total/2**20),flush=True);last=time.monotonic()
    if total!=spec['bytes'] or checksum.hexdigest()!=spec['sha256']:
        raise ValueError('Media checksum/size mismatch; incomplete file retained for inspection')
    partial.rename(out);print('Ubuntu OVA verified:',out,'seconds',round(time.monotonic()-started))


if __name__=='__main__':main()
