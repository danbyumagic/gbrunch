#!/usr/bin/env python3
"""Reset ONLY a named disposable QEMU fixture, retaining its Linux workspace."""
import pathlib,subprocess,struct,zlib,json
R=pathlib.Path(__file__).resolve().parents[2];W=pathlib.Path('/tmp/gbrunch-toolbox-test');F=pathlib.Path('/tmp/gbrunch-toolbox-v2-fixtures');disk=W/'usb-uefi.qcow2';iso=pathlib.Path('/dev/shm/gbrunch-toolbox-output/gbrunch-toolbox-v0.2-amd64.iso');img=R/'build/qemu11/qemu-img';io=R/'build/qemu11/qemu-io'
assert disk.parent==W and disk.is_file() and disk.suffix=='.qcow2'
info=json.loads(subprocess.check_output([str(img),'info','--output=json',str(disk)],text=True));assert info['virtual-size']==64000000000 and pathlib.Path(info['full-backing-filename'])==iso
primary=F/'fixture-primary.bin';subprocess.run([str(img),'dd','-f','qcow2','bs=512','count=64','if='+str(disk),'of='+str(primary)],check=True)
raw=primary.read_bytes();h=bytearray(raw[512:1024]);count,esz=struct.unpack_from('<II',h,80);assert (count,esz)==(248,128)
table=bytearray(raw[1024:1024+count*esz]);work=table[3*128:4*128];assert work[56:]==('GBWORK'.encode('utf-16le')+bytes(72-12))
with iso.open('rb') as f:f.seek(1024);fresh=f.read(count*esz)
table[:3*128]=fresh[:3*128];table[4*128:]=bytes(len(table)-4*128)
end=max((struct.unpack_from('<Q',table,i*128+40)[0]+1)*512 for i in range(3));start=struct.unpack_from('<Q',table,3*128+32)[0]*512;assert end<start
struct.pack_into('<I',h,88,zlib.crc32(table));struct.pack_into('<I',h,16,0);struct.pack_into('<I',h,16,zlib.crc32(h[:92]));last=struct.unpack_from('<Q',h,32)[0];ts=(len(table)+511)//512;bh=bytearray(h);struct.pack_into('<QQ',bh,24,last,1);struct.pack_into('<Q',bh,72,last-ts);struct.pack_into('<I',bh,16,0);struct.pack_into('<I',bh,16,zlib.crc32(bh[:92]))
for name,offset,data in [('table',1024,table),('header',512,h),('backup-table',(last-ts)*512,table),('backup-header',last*512,bh)]:
 p=F/('fixture-reset-'+name+'.bin');p.write_bytes(data);subprocess.run([str(io),'-f','qcow2','-c',f'write -s {p} {offset} {len(data)}',str(disk)],check=True,stdout=subprocess.DEVNULL)
print('DISPOSABLE_FIXTURE_RESET')
