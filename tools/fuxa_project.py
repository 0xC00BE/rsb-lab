"""Assemble the complete FUXA export with its verified, bundled artwork."""
import argparse
import base64
import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ASSET_REF = re.compile(r'rsb-asset:([a-f0-9]{20}\.(?:png|svg))')
DASHBOARDS = ('Dashboard-P1', 'Dashboard-P2', 'Dashboard-P3', 'Dashboard-P4')


def assemble(directory=None):
    directory = Path(directory or ROOT / 'projects/fuxa')
    project = json.loads((directory / 'project.json').read_text(encoding='utf-8'))
    manifest = json.loads((directory / 'assets-manifest.json').read_text())
    if manifest.get('schema_version') != 1:
        raise ValueError('Unsupported FUXA asset manifest')
    assets, expected = {}, {}
    for item in manifest['assets']:
        name = Path(item['path']).name
        if item['path'] != 'assets/' + name or not ASSET_REF.fullmatch('rsb-asset:' + name):
            raise ValueError('Invalid bundled artwork path')
        if name in assets:
            raise ValueError('Duplicate artwork manifest entry')
        path = directory / 'assets' / name
        if path.is_symlink():
            raise ValueError('Artwork symlinks are not supported')
        data = path.read_bytes()
        if len(data) != item['bytes'] or hashlib.sha256(data).hexdigest() != item['sha256']:
            raise ValueError('Artwork checksum mismatch: ' + name)
        mime = 'image/png' if name.endswith('.png') else 'image/svg+xml'
        if item['media_type'] != mime or (mime == 'image/png' and not data.startswith(b'\x89PNG\r\n\x1a\n')):
            raise ValueError('Artwork media type mismatch: ' + name)
        assets[name] = 'data:' + mime + ';base64,' + base64.b64encode(data).decode()
        expected[name] = item['references']
    if {p.name for p in (directory / 'assets').iterdir()} != set(assets):
        raise ValueError('Bundled artwork files differ from the manifest')
    counts = dict.fromkeys(assets, 0)

    def replace(match):
        name = match[1]
        if name not in assets:
            raise ValueError('Missing bundled artwork: ' + name)
        counts[name] += 1
        return assets[name]

    def walk(value):
        if isinstance(value, dict):
            return {k: walk(v) for k, v in value.items()}
        if isinstance(value, list):
            return [walk(v) for v in value]
        if isinstance(value, str):
            result = ASSET_REF.sub(replace, value)
            if 'rsb-asset:' in result:
                raise ValueError('Malformed artwork reference')
            return result
        return value

    project = walk(project)
    if counts != expected:
        raise ValueError('Artwork reference counts differ from the manifest')
    views = project['hmi']['views']
    ids = [v['id'] for v in views]
    if len(ids) != 4 or len(set(ids)) != 4 or tuple(v['name'] for v in views) != DASHBOARDS:
        raise ValueError('Expected only Dashboard-P1 through Dashboard-P4, in order')
    layout = project['hmi']['layout']
    if layout['start'] != ids[0]:
        raise ValueError('FUXA must start at Dashboard-P1')
    items = layout['navigation']['items']
    if [(item.get('view'), item.get('text')) for item in items] != list(zip(ids, DASHBOARDS)):
        raise ValueError('FUXA navigation must contain only the four current dashboards')
    if any(item.get('children') or item.get('link') for item in items):
        raise ValueError('Unexpected nested or external dashboard navigation')
    return project


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True,
                        help='Write a self-contained native FUXA import file.')
    args = parser.parse_args()
    if args.output.exists():
        raise RuntimeError('Output already exists; choose a new filename.')
    project = assemble()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('x', encoding='utf-8', newline='\n') as output:
        json.dump(project, output, ensure_ascii=False, separators=(',', ':'))
    print('Assembled Dashboard-P1 through P4 with all verified artwork:', args.output)


if __name__ == '__main__':
    main()
