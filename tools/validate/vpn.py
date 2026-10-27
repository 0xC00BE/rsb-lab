#!/usr/bin/env python3
"""Read-only reachability checks from an already connected administrator/student VPN client."""
import argparse
import concurrent.futures
import json
import socket


def probe(host,port,expected):
    connected=False
    try:
        with socket.create_connection((host,port),3):connected=True
    except OSError:pass
    result={'host':host,'port':port,'connected':connected,'expected':expected}
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('role',choices=['admin','student'])
    args=parser.parse_args()
    if args.role=='admin':
        rows=[('10.0.10.1',443,True),('10.0.10.2',445,True),('10.0.20.20',1880,True),
              ('10.0.30.10',1881,True),('10.0.30.30',3000,True),('10.0.40.10',1881,True),
              ('10.0.40.20',8080,True),('10.0.50.101',502,True),('10.0.50.116',20000,True)]
    else:
        rows=[('10.0.10.3',3389,True),('10.0.10.3',5985,True),('10.0.10.2',445,True),('10.0.30.40',8088,True),
              ('10.0.10.1',443,False),('10.0.20.1',443,False),('10.0.20.20',1880,False),
              ('10.0.30.30',3000,False),('10.0.40.10',1881,False),('10.0.40.20',8080,False),
              ('10.0.50.101',502,False),('10.0.50.116',20000,False)]
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
        results=list(pool.map(lambda row:probe(*row),rows))
    for result in results:print(json.dumps(result))
    if any(r['connected']!=r['expected'] for r in results):raise SystemExit(1)
    print('VPN '+args.role+' reachability checks passed.')


if __name__=='__main__':main()
