import hashlib
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
from fuxa_project import assemble, DASHBOARDS
from update_fuxa import recognized_project


class VisualProjectTests(unittest.TestCase):
    def test_current_project_contains_only_four_dashboards_and_bundled_artwork(self):
        result=assemble()
        self.assertEqual(tuple(v['name'] for v in result['hmi']['views']), DASHBOARDS)
        source=json.dumps(result)
        self.assertNotIn('rsb-asset:',source)
        self.assertEqual(source.count('data:image/'),38)
        self.assertNotIn('\ufffd',source)

    def test_update_accepts_known_views_and_rejects_custom_views(self):
        result=assemble()
        current={'devices':result['devices'], 'hmi':{'views':[
            {'id':view['id'],'name':view['name']} for view in result['hmi']['views']]}}
        self.assertTrue(recognized_project(current,result))
        self.assertTrue(recognized_project(result,result))
        current['hmi']['views'].append({'id':'custom-dashboard','name':'Operator custom screen'})
        self.assertFalse(recognized_project(current,result))

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
