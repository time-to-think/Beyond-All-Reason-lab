"""Cache an exact runtime archive of the checked-out game; never modify its source."""
import hashlib
import json
import os
from pathlib import Path
import zipfile


def pack_core(source, destination):
    source, destination = Path(source), Path(destination)
    files=[]
    for parent, dirs, names in os.walk(source):
        dirs[:] = sorted(d for d in dirs if d != '.git')
        for name in sorted(names):
            if name == '.git':
                continue
            path=Path(parent)/name
            info=path.stat()
            files.append((path,path.relative_to(source).as_posix(),info.st_size,info.st_mtime_ns))
    signature=hashlib.sha256(json.dumps([(n,s,t) for _,n,s,t in files]).encode()).hexdigest()
    manifest=destination.with_suffix('.manifest.json')
    if destination.exists() and manifest.exists() and json.loads(manifest.read_text()).get('signature')==signature:
        return
    destination.parent.mkdir(parents=True,exist_ok=True)
    temporary=destination.with_suffix('.partial')
    print('Preparing cached game archive ('+str(len(files))+' source files).',flush=True)
    with zipfile.ZipFile(temporary,'w',zipfile.ZIP_DEFLATED,compresslevel=1,allowZip64=True) as archive:
        for path,name,_,_ in files:
            archive.write(path,name)
    temporary.replace(destination)
    manifest.write_text(json.dumps(dict(signature=signature,files=len(files),source=str(source)),indent=2))
