import importlib.util
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

MODULE = Path(__file__).resolve().parents[1]/'tools/lab.py'
spec = importlib.util.spec_from_file_location('lab',MODULE)
lab = importlib.util.module_from_spec(spec)
spec.loader.exec_module(lab)

class ConfigurationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.env = {'LAB_DATA_DIR':'/srv/rsb-state',
                    **{f'VLAN{v}_PARENT':f'eth{v}' for v in lab.ZONES},
                    'FUXA_IMAGE':'example/fuxa@sha256:'+'a'*64}

    def check(self):
        with patch.object(lab,'env_file',return_value=self.env):
            return lab.check_configuration(linux=False)

    def test_rejects_filesystem_root(self):
        self.env['LAB_DATA_DIR']='/'
        with self.assertRaises(RuntimeError): self.check()

    def test_accepts_valid_configuration_without_runtime_probe(self):
        self.assertEqual(self.env,self.check())

    def test_rejects_duplicate_zone_interface(self):
        self.env['VLAN30_PARENT']=self.env['VLAN20_PARENT']
        with self.assertRaises(RuntimeError): self.check()

    def test_rejects_floating_image(self):
        self.env['FUXA_IMAGE']='example/fuxa:latest'
        with self.assertRaises(RuntimeError): self.check()

    def test_init_does_not_replace_existing_secrets(self):
        (self.root/'.env').write_text('private-existing-value')
        with patch.object(lab,'ROOT',self.root):
            with self.assertRaises(RuntimeError): lab.init()
        self.assertEqual('private-existing-value',(self.root/'.env').read_text())

    def test_init_generates_distinct_local_secrets(self):
        text='LAB_DATA_DIR=CHANGE_ME_ABSOLUTE_LINUX_STATE_DIRECTORY\nA=GENERATED_BY_INIT\nB=GENERATED_BY_INIT\n'
        (self.root/'.env.example').write_text(text)
        with patch.object(lab,'ROOT',self.root): lab.init()
        lines=(self.root/'.env').read_text().splitlines()
        self.assertNotEqual(lines[1].split('=',1)[1],lines[2].split('=',1)[1])
        self.assertNotIn('GENERATED_BY_INIT','\n'.join(lines))

if __name__ == '__main__': unittest.main()
