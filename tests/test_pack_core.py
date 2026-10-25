import importlib.util
from pathlib import Path
import tempfile
import unittest
import zipfile

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('pack_core',ROOT/'launcher/pack_core.py')
pack=importlib.util.module_from_spec(spec)
spec.loader.exec_module(pack)


class PackTests(unittest.TestCase):
    def test_exact_payload_excludes_git_and_refreshes_changes(self):
        with tempfile.TemporaryDirectory() as directory:
            base=Path(directory)
            source=base/'source'
            (source/'.git').mkdir(parents=True)
            (source/'.git/secret').write_text('do not package')
            (source/'modinfo.lua').write_text('return {}')
            output=base/'runtime/BAR.sdz'
            pack.pack_core(source,output)
            before=output.stat().st_mtime_ns
            pack.pack_core(source,output)
            self.assertEqual(before,output.stat().st_mtime_ns)
            with zipfile.ZipFile(output) as z:
                self.assertEqual(z.namelist(),['modinfo.lua'])
                self.assertEqual(z.read('modinfo.lua'),b'return {}')
            (source/'modinfo.lua').write_text('return {name="new"}')
            pack.pack_core(source,output)
            with zipfile.ZipFile(output) as z:
                self.assertEqual(z.read('modinfo.lua'),b'return {name="new"}')


if __name__=='__main__':
    unittest.main()
