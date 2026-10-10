#!/usr/bin/env python3
"""Replace only the ISO's standalone Markdown README, retaining every boot extent."""
import pathlib,struct,hashlib,json,sys
iso=pathlib.Path(sys.argv[1]);doc=pathlib.Path(sys.argv[2]).read_bytes();record=pathlib.Path(sys.argv[3])
assert iso.is_file() and iso.suffix=='.iso' and doc.startswith(b'# GBRUNCH Toolbox v0.2')
def sha():
 h=hashlib.sha256()
 with iso.open('rb') as f:
  for b in iter(lambda:f.read(4<<20),b''):h.update(b)
 return h.hexdigest()
before=sha()
with iso.open('r+b') as f:
 f.seek(16*2048);pvd=f.read(2048);assert pvd[:7]==b'\x01CD001\x01'
 root=pvd[156:];offset=struct.unpack_from('<I',root,2)[0]*2048;size=struct.unpack_from('<I',root,10)[0];f.seek(offset);directory=f.read(size);found=[];pos=0
 while pos<len(directory):
  n=directory[pos]
  if not n:pos=(pos//2048+1)*2048;continue
  row=directory[pos:pos+n];name=row[33:33+row[32]].decode(errors='replace')
  if name.upper().startswith('README') and '.MD' in name.upper():found.append((struct.unpack_from('<I',row,2)[0]*2048,struct.unpack_from('<I',row,10)[0]))
  pos+=n
 assert len(found)==1;start,length=found[0];assert len(doc)<=length
 f.seek(start);original=f.read(length);assert original.startswith(b'# GBRUNCH Toolbox v0.')
 f.seek(start);assert f.write(doc+bytes(b' ')*(length-len(doc)))==length;f.flush();__import__('os').fsync(f.fileno())
record.write_text(json.dumps(dict(before_sha256=before,after_sha256=sha(),changed_extent=dict(offset=start,bytes=length),scope='Standalone ISO README only; SquashFS, EFI, kernel, initrd and GPT extents unchanged'),indent=2)+'\n')
print(record.read_text())
