import hashlib
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
from fuxa_project import assemble


class VisualProjectTests(unittest.TestCase):
    def test_complete_project_has_all_assets_and_original_views(self):
        result=assemble()
        old=json.loads((ROOT/'projects/fuxa/process.fuxap').read_text())
        self.assertEqual(len(result['hmi']['views']),26)
        self.assertTrue({v['id'] for v in old['hmi']['views']}.issubset({v['id'] for v in result['hmi']['views']}))
        source=json.dumps(result)
        self.assertNotIn('rsb-asset:',source)
        self.assertEqual(source.count('data:image/'),80)
        self.assertNotIn('\ufffd',source)

    def test_corrupt_asset_fails_before_import(self):
        with tempfile.TemporaryDirectory() as tmp:
            target=Path(tmp)/'fuxa';shutil.copytree(ROOT/'projects/fuxa',target)
            manifest=json.loads((target/'assets-manifest.json').read_text())
            (target/manifest['assets'][0]['path']).write_bytes(b'changed')
            with self.assertRaisesRegex(ValueError,'checksum mismatch'):assemble(target)

    def test_asset_path_cannot_escape_bundle(self):
        with tempfile.TemporaryDirectory() as tmp:
            target=Path(tmp)/'fuxa';shutil.copytree(ROOT/'projects/fuxa',target)
            path=target/'assets-manifest.json';manifest=json.loads(path.read_text())
            manifest['assets'][0]['path']='../../outside.svg';path.write_text(json.dumps(manifest))
            with self.assertRaisesRegex(ValueError,'artwork path'):assemble(target)


if __name__=='__main__':unittest.main()
