#!/usr/bin/env python3
"""Read recent historian measurements and execute each provisioned Grafana panel."""
import base64
import copy
import csv
import io
import json
import sys
import time
import urllib.request
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from lab import ROOT, env_file


def main():
    env = env_file()
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))

    def request(url, data=None, headers=None):
        req = urllib.request.Request(url, data=data, headers=headers or {})
        with opener.open(req, timeout=30) as response:
            return response.read()

    query = 'from(bucket:"brewery") |> range(start:-2m) |> group(columns:["_measurement"]) |> count()'
    data = request('http://10.0.30.20:8086/api/v2/query?org=brewery', query.encode(),
        {'Authorization': 'Token ' + env['INFLUXDB_TOKEN'],
         'Content-Type': 'application/vnd.flux', 'Accept': 'application/csv'})
    rows = list(csv.DictReader(io.StringIO(data.decode())))
    expected = {'raw_materials', 'brewhouse', 'fermentation', 'conditioning', 'packaging', 'utilities'}
    found = {row['_measurement'] for row in rows if row.get('_measurement') and int(row.get('_value') or 0) > 0}
    if found != expected:
        raise RuntimeError('Recent historian measurements are incomplete: ' + str(found))
    print('Recent InfluxDB records verified for all six cells.')
    dashboard = json.loads(request('http://10.0.30.30:3000/api/dashboards/uid/rsb-brewery-operations'))['dashboard']
    source = json.loads((ROOT / 'vlan30/grafana/dashboards/brewery.json').read_text())
    if {p['title'] for p in dashboard['panels']} != {p['title'] for p in source['panels']}:
        raise RuntimeError('Provisioned dashboard panels differ from the source')
    authorization = base64.b64encode(('admin:' + env['GRAFANA_PASSWORD']).encode()).decode()
    now = int(time.time() * 1000)
    for panel in dashboard['panels']:
        target = copy.deepcopy(panel['targets'][0])
        target.update(refId='validation', intervalMs=5000, maxDataPoints=1000)
        payload = {'queries': [target], 'from': str(now - 120000), 'to': str(now)}
        result = json.loads(request('http://10.0.30.30:3000/api/ds/query', json.dumps(payload).encode(),
            {'Authorization': 'Basic ' + authorization, 'Content-Type': 'application/json'}))
        query_result = result.get('results', {}).get('validation', {})
        frames = query_result.get('frames', [])
        timestamps = [stamp for frame in frames for stamp in frame.get('data', {}).get('values', [[]])[0]]
        if query_result.get('error') or not timestamps:
            raise RuntimeError('Grafana panel returned no data: ' + panel['title'])
        if max(timestamps) < now - 30000:
            raise RuntimeError('Grafana panel is stale: ' + panel['title'])
        print('Fresh panel data:', panel['title'])


if __name__ == '__main__':
    main()
