"""Build two original, deterministic SMF/SMT test maps using only the standard library.

Binary layout reference: RecoilEngine/rts/Map/SMF/SMFFormat.h (GPL-2.0-or-later).
Generated geometry and palette textures are original project assets.
"""
import argparse
from array import array
import hashlib
import json
import math
from pathlib import Path
import struct
import sys
import zipfile

SIZE = 1024
WORLD = SIZE * 8
MIN_HEIGHT, MAX_HEIGHT = -160.0, 640.0
SPECS = {
    'ridge': {'name': 'BAR Lab Ridge Pass v1', 'description': 'Symmetric ridge with one central ground passage.',
              'starts': [[1400, 4096], [6792, 4096]]},
    'river': {'name': 'BAR Lab Twin Crossings v1', 'description': 'Symmetric river with two land crossings; aircraft can cross anywhere.',
              'starts': [[1400, 4096], [6792, 4096]]},
}
PALETTE = [(106, 130, 79), (129, 119, 96), (85, 88, 91), (69, 105, 132), (159, 142, 104)]


def smooth(value):
    value = max(0, min(1, value))
    return value*value*(3-2*value)


def height(kind, x, z):
    """World coordinates; both geometries have exact 180-degree symmetry."""
    if kind == 'ridge':
        ridge = 1-smooth((abs(x-WORLD/2)-180)/180)
        passage = smooth((abs(z-WORLD/2)-480)/160)
        return 80+440*ridge*passage
    if kind == 'river':
        river = 1-smooth((abs(x-WORLD/2)-440)/200)
        crossing_distance = min(abs(z-2600), abs(z-(WORLD-2600)))
        outside_crossing = smooth((crossing_distance-360)/140)
        return 80-200*river*outside_crossing
    raise ValueError('Unknown map kind')


def color_index(h):
    if h < 0:
        return 3
    if h < 65:
        return 4
    if h < 130:
        return 0
    if h < 350:
        return 1
    return 2


def dxt_block(rgb):
    r, g, b = rgb
    color = ((r >> 3) << 11) | ((g >> 2) << 5) | (b >> 3)
    return struct.pack('<HHI', color, max(0, color-1), 0)


def map_bytes(kind):
    values = array('H', (round((height(kind, x*8, z*8)-MIN_HEIGHT)/(MAX_HEIGHT-MIN_HEIGHT)*65535)
                         for z in range(SIZE+1) for x in range(SIZE+1)))
    if sys.byteorder != 'little':
        values.byteswap()
    heights = values.tobytes()
    type_map = bytes((SIZE//2)**2)
    tile_ids = array('I', (color_index(height(kind, (x+.5)*32, (z+.5)*32))
                          for z in range(SIZE//4) for x in range(SIZE//4)))
    if sys.byteorder != 'little':
        tile_ids.byteswap()
    tile_chunk = struct.pack('<iii', 1, len(PALETTE), len(PALETTE)) + b'lab.smt\0' + tile_ids.tobytes()
    minimap = bytearray()
    for pixels in (1024, 512, 256, 128, 64, 32, 16, 8, 4):
        for z in range(pixels//4):
            for x in range(pixels//4):
                h = height(kind, (x*4+2)*WORLD/pixels, (z*4+2)*WORLD/pixels)
                minimap.extend(dxt_block(PALETTE[color_index(h)]))
    assert len(minimap) == 699048
    metal = bytes((SIZE//2)**2)
    features = struct.pack('<ii', 0, 0)
    chunks = [heights, type_map, tile_chunk, minimap, metal, features]
    pointers, offset = [], 80
    for chunk in chunks:
        pointers.append(offset)
        offset += len(chunk)
    map_id = int.from_bytes(hashlib.sha256(kind.encode()).digest()[:4], 'little') & 0x7fffffff
    header = struct.pack('<16s7i2f7i', b'spring map file\0', 1, map_id, SIZE, SIZE, 8, 8, 32,
                         MIN_HEIGHT, MAX_HEIGHT, *pointers, 0)
    assert len(header) == 80
    tiles = struct.pack('<16s4i', b'spring tilefile\0', 1, len(PALETTE), 32, 1)
    tiles += b''.join(dxt_block(rgb)*85 for rgb in PALETTE)
    return header+b''.join(chunks), tiles


def mapinfo(kind):
    spec = SPECS[kind]
    return f'''return {{
 name = "{spec['name']}", description = "{spec['description']}",
 author = "Personal BAR Lab", version = "", modtype = 3,
 mapfile = "maps/lab.smf", depend = {{"Map Helper v1"}},
 notdeformable = true, gravity = 130, tidalstrength = 0,
 maxmetal = 0, extractorradius = 100, maphardness = 200,
 atmosphere = {{ minwind = 10, maxwind = 10, fogstart = 0.8,
                 skycolor = {{0.55, 0.7, 0.85}}, cloudcolor = {{0.8, 0.8, 0.8}} }},
 lighting = {{ sundir = {{0.7, 1, 0.4}}, groundambientcolor = {{0.55,0.55,0.55}},
               grounddiffusecolor = {{0.8,0.8,0.8}}, unitambientcolor = {{0.6,0.6,0.6}} }},
 water = {{ damage = 0, surfacecolor = {{0.25,0.45,0.6}}, surfacealpha = 0.6 }},
 teams = {{ [0] = {{startpos = {{x=1400, z=4096}}}}, [1] = {{startpos = {{x=6792, z=4096}}}} }},
 terraintypes = {{[0] = {{name="Ground", hardness=1, movespeeds={{tank=1,kbot=1,hover=1,ship=1}}}}}},
}}
'''


def preview(kind, destination):
    """Small self-contained SVG overview; not a game screenshot."""
    cells = []
    for z in range(64):
        for x in range(64):
            rgb = PALETTE[color_index(height(kind, (x+.5)*128, (z+.5)*128))]
            cells.append(f'<rect x="{x*8}" y="{z*8}" width="8" height="8" fill="rgb{rgb}"/>')
    for i, (x, z) in enumerate(SPECS[kind]['starts']):
        cells.append(f'<circle cx="{x/16}" cy="{z/16}" r="12" fill="{"#29b6f6" if i==0 else "#ff7043"}" stroke="white" stroke-width="2"/>')
    destination.write_text('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 548">'+
        ''.join(cells)+f'<text x="12" y="537" font-family="sans-serif" font-size="19">{SPECS[kind]["name"]}</text></svg>', encoding='utf-8')


def build_all(destination):
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=True)
    signature = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    manifest_path = destination/'manifest.json'
    if manifest_path.exists():
        old = json.loads(manifest_path.read_text())
        if old.get('generator_sha256') == signature and all(
                (destination/(kind+'.sdz')).exists() and hashlib.sha256((destination/(kind+'.sdz')).read_bytes()).hexdigest()==old['maps'][kind]['sha256'] for kind in SPECS):
            return old
    manifest = dict(generator_sha256=signature, map_size=[WORLD, WORLD], maps={})
    for kind, spec in SPECS.items():
        smf, smt = map_bytes(kind)
        archive = destination/(kind+'.sdz')
        with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED, compresslevel=6) as z:
            for name, data in [('mapinfo.lua', mapinfo(kind).encode()), ('maps/lab.smf', smf), ('maps/lab.smt', smt)]:
                info = zipfile.ZipInfo(name, (2026, 1, 1, 0, 0, 0))
                info.compress_type = zipfile.ZIP_DEFLATED
                z.writestr(info, data)
        preview(kind, destination/(kind+'.svg'))
        manifest['maps'][kind] = dict(spec, archive=archive.name, sha256=hashlib.sha256(archive.read_bytes()).hexdigest())
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    return manifest


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('destination', type=Path)
    args = parser.parse_args()
    print(json.dumps(build_all(args.destination), indent=2))
