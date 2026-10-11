#!/usr/bin/env python3
"""Locally graft vendor files into a new EROFS image, preserving inode metadata."""
import argparse, hashlib, io, json, pathlib, runpy, shutil, struct, subprocess, tarfile, tempfile
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--vendor',required=True,type=pathlib.Path)
p.add_argument('--mapping',required=True,type=pathlib.Path,help='JSON list: path, source, optional metadata_from')
p.add_argument('--output',required=True,type=pathlib.Path)
p.add_argument('--dump-erofs',default='dump.erofs')
p.add_argument('--mkfs-erofs',default='mkfs.erofs')
p.add_argument('--fsck-erofs',default='fsck.erofs')
a=p.parse_args()
if a.output.exists():p.error('Output must be a new file')
if not a.vendor.is_file() or str(a.vendor.resolve()).startswith('/dev/'):p.error('Vendor must be a regular file')
items=json.loads(a.mapping.read_text());paths=[]
for item in items:
    target=pathlib.PurePosixPath(item['path'])
    if target.is_absolute() or '..' in target.parts or not target.parts:p.error('Unsafe vendor path')
    source=pathlib.Path(item['source']).resolve()
    if not source.is_file() or str(source).startswith('/dev/'):p.error('Sources must be regular local files')
    item['source']=source
    original=pathlib.PurePosixPath(item.get('metadata_from',str(target)))
    if original.is_absolute() or '..' in original.parts:p.error('Unsafe metadata path')
    item['original']=str(original);paths.append(str(target))
if len(paths)!=len(set(paths)):p.error('Duplicate vendor target')
meta=runpy.run_path(str(pathlib.Path(__file__).resolve().parents[1]/'third_party/gbos-vm/erofs_metadata.py'))['metadata']
meta.__globals__['D']=pathlib.Path(shutil.which(a.dump_erofs) or a.dump_erofs)
with a.vendor.open('rb') as f:
    f.seek(1024);sb=f.read(128)
    if sb[:4]!=bytes.fromhex('e2e1f5e0'):p.error('Input is not EROFS')
    bs=1<<sb[12];root=struct.unpack_from('<I',sb,40)[0]*bs+struct.unpack_from('<H',sb,14)[0]*32
    f.seek(root);oldroot=f.read(64)
    if oldroot[0]&1:p.error('This experimental graft requires a compact root inode')
a.output.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(a.vendor,a.output)
def run(args):return subprocess.run([str(v) for v in args],check=True,capture_output=True)
with tempfile.TemporaryDirectory(prefix='gbrunch-vendor-graft-') as td:
    overlay=pathlib.Path(td)/'overlay.tar';parents={'.'}
    for path in paths:
        parts=pathlib.PurePosixPath(path).parts[:-1]
        for n in range(1,len(parts)+1):parents.add('/'.join(parts[:n]))
    with tarfile.open(overlay,'w',format=tarfile.PAX_FORMAT) as tar:
        for target in sorted(parents):
            m=meta(a.vendor,'/' if target=='.' else '/'+target)
            ti=tarfile.TarInfo(target);ti.type=tarfile.DIRTYPE;ti.mode=m['mode']&0o7777;ti.uid=m['uid'];ti.gid=m['gid'];ti.mtime=m['mtime']
            ti.pax_headers={} if target=='.' else {'SCHILY.xattr.'+k:v.decode() for k,v in m['xattrs'].items()};tar.addfile(ti)
        for item in items:
            m=meta(a.vendor,'/'+item['original']);ti=tarfile.TarInfo(item['path']);ti.mode=m['mode']&0o7777;ti.uid=m['uid'];ti.gid=m['gid'];ti.mtime=m['mtime'];ti.size=item['source'].stat().st_size
            ti.pax_headers={'SCHILY.xattr.'+k:v.decode() for k,v in m['xattrs'].items()}
            with item['source'].open('rb') as f:tar.addfile(ti,f)
    run([a.mkfs_erofs,'--incremental=data','--tar=f','-x0','-b4096','-T1230768000','-zlz4hc',a.output,overlay])
with a.output.open('r+b') as f:
    f.seek(root);newroot=f.read(64)
    if newroot[0]&1 or newroot[2:4]!=oldroot[2:4]:raise RuntimeError('Root inode layout changed; output is not validated')
    f.seek(root+32);f.write(oldroot[32:48]);f.seek(1024);block=bytearray(f.read(bs-1024));block[4:8]=bytes(4);crc=0xffffffff
    for value in block:
        crc^=value
        for _ in range(8):crc=(crc>>1)^(0x82f63b78 if crc&1 else 0)
    f.seek(1028);f.write(struct.pack('<I',crc))
run([a.fsck_erofs,a.output])
for item in items:
    got=run([a.dump_erofs,'--path=/'+item['path'],'--cat',a.output]).stdout
    with item['source'].open('rb') as f:expected=hashlib.file_digest(f,'sha256').digest()
    if hashlib.sha256(got).digest()!=expected:raise RuntimeError('Readback failed: '+item['path'])
print(f'Validated private vendor image: {a.output}')
print('Rebuild the local virtual-disk partition layout if this image exceeds its previous partition size. Do not distribute Google-derived outputs.')
