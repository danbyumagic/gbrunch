#!/usr/bin/env python3
"""Fetch pinned official x86 Cuttlefish donor, extract only vendor and software HALs.
Sparse-super reads do not materialize the full logical disk.
"""
import bisect, hashlib, json, os, pathlib, re, struct, subprocess, urllib.request, zipfile
from inspect_recovery import liblp
ROOT = pathlib.Path(__file__).resolve().parents[1]
lock = json.loads((ROOT/'evidence/cuttlefish-x86-download.json').read_text())
path = ROOT/'downloads/cuttlefish-x86-16373615.zip'
def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        while b := f.read(8<<20): h.update(b)
    return h.hexdigest()
if not path.exists():
    html = urllib.request.urlopen(lock['page'], timeout=30).read(1<<20).decode()
    url = json.loads(re.search(r'var JSVariables = (\{.*?\});', html).group(1))['artifactUrl']
    part = path.with_suffix('.part')
    with urllib.request.urlopen(url, timeout=60) as f, part.open('wb') as out:
        while b := f.read(8<<20): out.write(b)
    assert sha(part) == lock['sha256']; part.rename(path)
assert sha(path) == lock['sha256']
base = ROOT/'extracted/cuttlefish-x86'; base.mkdir(exist_ok=True)
with zipfile.ZipFile(path) as z:
    if not (base/'super.img').exists(): z.extract('super.img', base)
with (base/'super.img').open('rb') as f:
    magic, major, minor, hs, cs, bs, nb, nc, crc = struct.unpack('<IHHHHIIII', f.read(28))
    assert magic == 0xed26ff3a and major == 1
    f.seek(hs); chunks = []; pos = 0
    for i in range(nc):
        start = f.tell(); kind, reserved, n, total = struct.unpack_from('<HHII', f.read(cs))
        chunks.append((pos, pos+n*bs, kind, start+cs)); pos += n*bs; f.seek(start+total)
    starts = [c[0] for c in chunks]
    class Sparse:
        def __init__(self): self.pos = 0
        def seek(self, pos): self.pos = pos
        def read(self, n):
            out = bytearray()
            while n:
                i = bisect.bisect_right(starts, self.pos)-1
                a, z, t, o = chunks[i]; size = min(n, z-self.pos); assert size > 0
                if t == 0xcac1: f.seek(o+self.pos-a); data = f.read(size)
                elif t == 0xcac2:
                    f.seek(o); pattern = f.read(4); start = (self.pos-a)%4
                    data = (pattern*((size+7)//4))[start:start+size]
                elif t == 0xcac3: data = bytes(size)
                else: raise ValueError(hex(t))
                assert len(data) == size
                out.extend(data); self.pos += size; n -= size
            return bytes(out)
    image = Sparse(); meta = liblp(image, 0)
    (ROOT/'evidence/cuttlefish-super.json').write_text(json.dumps(meta, indent=2)+'\n')
    for partition in ['vendor', 'vendor_dlkm', 'system_dlkm']:
        part = next(p for p in meta['slots'][0]['partitions'] if p['name'] == partition+'_a')
        with (base/(partition+'.img')).open('wb') as out:
            for e in part['extents']:
                assert e['target_type'] == 0 and e['source'] == 0
                image.seek(e['absolute_offset']); left = e['bytes']
                while left: n = min(left, 4<<20); out.write(image.read(n)); left -= n
local = ROOT/'tools/local'; env = os.environ.copy()
env['LD_LIBRARY_PATH'] = str(local/'usr/lib/x86_64-linux-gnu')
extraction = '--extract' if (base/'vendor-files').exists() else f'--extract={base}/vendor-files'
flags = [] if (base/'vendor-files').exists() else ['--no-preserve']
subprocess.run([str(local/'usr/bin/fsck.erofs'), extraction,
    *flags, str(base/'vendor.img')], env=env, check=True)
for name in ['com.android.hardware.keymint.rust_nonsecure', 'com.android.hardware.gatekeeper.nonsecure', 'com.android.hardware.boot']:
    directory = base/name; directory.mkdir(exist_ok=True)
    with zipfile.ZipFile(base/'vendor-files/apex'/f'{name}.apex') as z: z.extract('apex_payload.img', directory)
    payload = directory/'payload'; payload.mkdir(exist_ok=True)
    if not any(payload.rglob('*.rc')):
        p = subprocess.run([str(local/'usr/sbin/debugfs'), '-R', f'rdump / {payload}',
            str(directory/'apex_payload.img')], env=env, capture_output=True, text=True, check=True)
        (directory/'extract.log').write_text(p.stdout+p.stderr)
    assert any(payload.rglob('*.rc')), 'debugfs can report errors with success exit status'
subprocess.run(['python3', str(ROOT/'tools/stage_security.py')], check=True)
