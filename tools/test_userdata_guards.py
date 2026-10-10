#!/usr/bin/env python3
"""Pure GPT rejection/planning tests; no physical disk or VM required."""
import pathlib,tempfile,struct,zlib,json
from maintain_userdata_guest import layout,plan_target
R=pathlib.Path(__file__).resolve().parents[1]
original=(R/'build/userdata-maintenance/test/prefix.bin').read_bytes()
with tempfile.TemporaryDirectory() as td:
    f=pathlib.Path(td)/'fixture.raw';size=128<<30;last=size//512-1
    h=bytearray(original[512:1024]);table=bytearray(original[1024:17408]);struct.pack_into('<Q',h,32,last);struct.pack_into('<Q',h,48,last-33)
    def write(table):
        struct.pack_into('<I',h,88,zlib.crc32(table));struct.pack_into('<I',h,16,0);struct.pack_into('<I',h,16,zlib.crc32(h[:92]))
        b=bytearray(h);struct.pack_into('<QQ',b,24,last,1);struct.pack_into('<Q',b,72,last-32);struct.pack_into('<I',b,16,0);struct.pack_into('<I',b,16,zlib.crc32(b[:92]))
        with f.open('wb') as out:
            out.truncate(size);out.seek(0);out.write(original[:512]+h+table);out.seek((last-32)*512);out.write(table+b)
    write(table);parts,u,*rest=layout(f);start,length,_=plan_target(parts,rest[1],rest[3],size)
    assert start<24<<30 and start+length<last*512,'End-of-drive GPT must not consume unused space'
    try:plan_target(parts,rest[1],rest[3],32<<30)
    except AssertionError:pass
    else:raise AssertionError('Insufficient capacity accepted')
    with f.open('r+b') as out:out.seek(1024);out.write(b'X')
    try:layout(f)
    except AssertionError:pass
    else:raise AssertionError('Bad GPT CRC accepted')
    table[16:32]=bytes(16);write(table)
    try:layout(f)
    except AssertionError:pass
    else:raise AssertionError('Wrong userdata identity accepted')
result={'normal_end_of_disk_backup_supported':True,'insufficient_space_rejected':True,'corrupt_table_rejected':True,'wrong_userdata_identity_rejected':True}
(R/'evidence/userdata-guard-tests.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
