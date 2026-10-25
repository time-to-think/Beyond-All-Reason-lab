"""Generated map geometry, archive offsets and reproducibility contracts."""
import importlib.util
from pathlib import Path
import struct
import tempfile
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('build_maps', ROOT/'maps/build_maps.py')
maps = importlib.util.module_from_spec(spec)
spec.loader.exec_module(maps)


class MapTests(unittest.TestCase):
    def test_rotational_symmetry_and_flat_starts(self):
        for kind in maps.SPECS:
            for x in range(0,8193,128):
                for z in range(0,8193,128):
                    self.assertAlmostEqual(maps.height(kind,x,z), maps.height(kind,8192-x,8192-z))
            for x,z in maps.SPECS[kind]['starts']:
                for dx,dz in ((0,0),(0,200),(300,0),(150,380)):
                    self.assertEqual(maps.height(kind,x+dx,z+dz), 80)

    def test_pass_and_crossings_are_ground_routes(self):
        self.assertGreater(maps.height('ridge',4096,1000), 500)
        self.assertEqual(maps.height('ridge',4096,4096), 80)
        self.assertLess(maps.height('river',4096,4096), -100)
        for z in (2600,5592):
            for x in range(0,8193,32):
                self.assertEqual(maps.height('river',x,z),80)

    def test_archive_layout_and_determinism(self):
        with tempfile.TemporaryDirectory() as directory:
            dest = Path(directory)
            first = maps.build_all(dest)
            self.assertEqual(first, maps.build_all(dest))
            for kind in maps.SPECS:
                with zipfile.ZipFile(dest/(kind+'.sdz')) as archive:
                    raw=archive.read('maps/lab.smf')
                    header=struct.unpack('<16s7i2f7i',raw[:80])
                    self.assertEqual(header[0], b'spring map file\0')
                    self.assertEqual(header[3:5],(1024,1024))
                    pointers=header[10:16]
                    self.assertEqual(pointers[0],80)
                    self.assertEqual(pointers[1]-pointers[0],1025*1025*2)
                    self.assertEqual(pointers[4]-pointers[3],699048)
                    self.assertEqual(len(raw)-pointers[5],8)
                    self.assertEqual(len(archive.read('maps/lab.smt')),32+len(maps.PALETTE)*680)


if __name__ == '__main__':
    unittest.main()
